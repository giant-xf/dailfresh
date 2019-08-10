import os
from django.shortcuts import render,redirect
from django.http import JsonResponse
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.db import transaction
from django.conf import settings
from goods.models import GoodsSKU
from user.models import Address
from order.models import OrderInfo,OrderGoods
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection

from datetime import datetime
from alipay import AliPay
# Create your views here.
# form表单提交, 每个商品选项框加一个name和values值，只有选中的values值才会被提交
# 需要接收的参数：商品id(sku_id)
# /order/place
class OrderPlaceViews(LoginRequiredMixin,View):
    '''订单提交页面显示'''
    def post(self, request):
        '''订单提交页面'''
        # 获取登入的用户
        user = request.user
        # 获取数据
        sku_ids = request.POST.getlist('sku_ids')   # [1,26]

        # 数据校验
        if not sku_ids :
            # 跳转到指定页面
            return redirect(reverse('cart:show'))

        # 拼接出redis链接
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id

        skus =[]
        total_count = 0
        total_price = 0
        # 遍历sku_ids获取用户需要购买的商品id
        for sku_id in sku_ids:
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取商品数量
            count = conn.hget(cart_key,sku_id)
            # 计算出商品小计
            amount = sku.price*int(count)
            # 动态添加属性
            sku.amount = amount
            sku.count =count
            # 添加到新的列表
            skus.append(sku)
            # 累加出商品的总件数和总价格
            total_count +=int(count)
            total_price +=amount

        # 运费：实际开发的时候，属于一个子系统，在一个表中有相应的计算规则
        # 这里我们直接规定
        transit_price = 10

        # 实付款
        total_pay = total_price+transit_price

        # 获取用户的收货地址
        address = Address.objects.filter(user=user)

        sku_ids =','.join(sku_ids)  # [1,26]--> 1,26

        # 组织上下文
        context = {'skus':skus,
                   'sku_ids':sku_ids,
                   'total_count':total_count,
                   'total_price':total_price,
                   'transit_price':transit_price,
                   'total_pay':total_pay,
                   'address':address}
        return render(request,'place_order.html',context)

# 采用ajax  post请求
# 需要获取的前端数据：地址id(addr_id),支付方式(pay_method),需要购买的商品id的字符串(sku_ids)
# 悲观锁
# /order/commit
class OrderCommitViews1(View):
    '''订单创建'''
    # 添加一个MySQL事务
    @transaction.atomic
    def post(self,request):
        '''订单创建'''
        # 获取用户
        user = request.user
        # 判断用户是否登入
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取数据
        # 获取地址id，付款方式id，商品id
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')   # 1,3  字符串
        # 数据校验
        if not all([addr_id,pay_method,sku_ids]):
            return JsonResponse({'res': 1, 'errmsg':'数据不完整'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg':'支付方式非法'})


        # 查询地址和商品是否存在，
        try:
            addr = Address.objects.get(user=user,id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg':'地址不存在'})

        # 业务处理:创建订单
        # todo 创建订单核心业务
            # 分析现在创建订单还缺少哪些参数(order_id,total_count,total_price,transit_price)
        # 组织参数
        # 订单id：20190806181130+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)

        # 运费
        transit_price = 10
        #总商品和总金额
        total_count = 0
        total_price = 0

        # 创建一个事务保存点
        save_point = transaction.savepoint()

        try:
            # todo 向df_order_info表中添加一条订单记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # todo 用户订单中有几个商品,就需要向df_order_goods表中添加几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id
            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品信息
                try:
                    # 悲观锁: select * from df_goods_sku where id=sku_id for update;
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    # 未找到商品
                    # 事务回滚
                    transaction.savepoint_rollback(save_point)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                # print('user:%d  stock:%d'%(sku.id,sku.stock))
                # import time
                # time.sleep(10)

                # 从redis中获取用户需要购买的商品的数量
                count = conn.hget(cart_key, sku_id)
                # 商品价格小计
                amount = sku.price*int(count)
                #添加记录时先判断库存
                if int(count) > sku.stock:
                    # 事务回滚
                    transaction.savepoint_rollback(save_point)
                    return JsonResponse({'res': 6, 'errmsg': '该商品库存不足'})
                # todo 向df_order_goods表中添加一条记录
                # 需要的参数：订单(order_id)、商品(sku)、商品数量(count)和商品价格(price)
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)
                # todo 更新商品的销量和库存
                sku.stock -=int(count)
                sku.sales +=int(count)
                sku.save()
                # todo 累加计算出订单商品的总数量和总价格
                total_count +=int(count)
                total_price +=amount

            # todo 更新订单信息表中商品的总数量和总价格
            order.total_count=total_count
            order.total_price=total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_point)
            return JsonResponse({'res':7,'errmsg':'提交订单失败'})

        # 如果执行不出错,则事务提交,从sace_point保存点开始提交
        transaction.savepoint_commit(save_point)

        # todo 清除用户购物车对应的记录
        # *list,对列表进行拆包，效果相当于遍历
        conn.hdel(cart_key,*sku_ids)
        # 返回应答
        return JsonResponse({'res': 5, 'message': '订单创建成功'})

# 乐观锁
class OrderCommitViews(View):
    '''订单创建'''

    @transaction.atomic
    def post(self, request):
        '''订单创建'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')  # 1,3

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})

        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            # 地址不存在
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # todo: 创建订单核心业务

        # 组织参数
        # 订单id: 20171122181630+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # todo: 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品的信息
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        # 商品不存在
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 5, 'errmsg': '商品不存在'})

                    # 从redis中获取用户所要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # todo: 判断商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                    # todo: 更新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # print('user:%d times:%d stock:%d' % (user.id, i, sku.stock))
                    # import time
                    # time.sleep(10)

                    # update df_goods_sku set stock=new_stock, sales=new_sales
                    # where id=sku_id and stock = orgin_stock

                    # 返回受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock,
                                                                                       sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 尝试的第3次
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败2'})
                        continue

                    # todo: 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # todo: 累加计算订单商品的总数量和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount

                    # 跳出循环
                    break

            # todo: 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # todo: 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 4, 'message': '创建成功'})

# 采用ajax  post请求
# 前端需要传递的参数:订单id(order_id)
# /order/pay
class OrderPayViews(View):
    '''订单支付'''
    def post(self,request):
        '''订单支付'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':1, 'errmsg':'用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 2, 'errmsg': '无效的订单id'})
        try:
            order = OrderInfo.objects.get(user=user,
                                          order_id=order_id,
                                          order_status=1,
                                          pay_method=3)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '订单错误'})
        # 业务处理：使用python sdk调用支付宝的支付接口
        # 初始化
        # app_private_key_string = open(os.path.join(settings.BASE_DIR,"apps/order/app_private_key.pem")).read()
        # alipay_public_key_string = open(os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.pem")).read()
        alipay = AliPay(
            appid="2016092800614150",   # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR,"apps/order/app_private_key.pem"),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.pem"),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug = True  # 默认False
        )

        # 调用支付宝接口
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price  # 订单总金额
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单id
            total_amount=str(total_pay),  # 支付宝总金额
            subject='悦购%s'%order_id,  # 订单标题
            return_url=None,
            notify_url=None
        )
        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?'+order_string
        return JsonResponse({'res':4,'pay_url':pay_url})


# 采用ajax  post请求
# 前端需要传递的参数:订单id(order_id)
# /order/check
class CheckPayViews(View):
    '''查看订单支付的结果'''
    def post(self,request):
        '''查看订单支付结果'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 1, 'errmsg': '用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 2, 'errmsg': '无效的订单id'})
        try:
            order = OrderInfo.objects.get(user=user,
                                          order_id=order_id,
                                          order_status=1,
                                          pay_method=3)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '订单错误'})
        # 业务处理：使用python sdk调用支付宝的支付接口
        # 初始化
        # app_private_key_string = open(os.path.join(settings.BASE_DIR,"apps/order/app_private_key.pem")).read()
        # alipay_public_key_string = open(os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.pem")).read()
        alipay = AliPay(
            appid="2016092800614150",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, "apps/order/app_private_key.pem"),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_path=os.path.join(settings.BASE_DIR, "apps/order/alipay_public_key.pem"),
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        while True:
            response = alipay.api_alipay_trade_query(order_id)
            # response = {
            #         "trade_no": "2017032121001004070200176844",   # 支付宝交易号
            #         "code": "10000",  # 接口调用是否成功
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS",  # 支付结果
            #         "total_amount": "20.00"
            # }

            # 获取接口调用是否成功代码
            code = response.get('code')

            if code =='10000' and response.get('trade_status') == "TRADE_SUCCESS":
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4  # 待评价状态
                order.save()
                # 返回结果
                return JsonResponse({'res':4,'message':'支付成功'})
            elif code == '40004' or (code =='10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                return JsonResponse({'res': 5, 'errmsg': '支付失败'})

class CommentViews(View):
    '''订单评论页面'''
    def get(self,request, order_id):
        '''提交评论页面'''
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id,user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单的商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)

        for order_sku in order_skus:
            # 计算商品小计
            amount = order_sku.count*order_sku.price
            # 动态的给order_sku添加amount属性,保存商品小计
            order_sku.amount = amount
        # 动态的给order添加order_skus属性,保存商品的订单信息
        order.order_skus = order_skus

        # 使用模板
        return render(request,'order_comment.html',{'order':order})

    def post(self,request, order_id):
        '''处理评论内容'''
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))

        # 获取评论的条数
        total_count = request.POST.get('total_count')
        total_count = int(total_count)
        for i in range(1,total_count+1):
            # 获取评论的商品的id
            sku_id = request.POST.get('sku_%d' % i)   # sku_1,sku_2
            # 获取商品的评论内容
            content=  request.POST.get('content_%d' % i,'')   # cotent_1 cotent_2
            try:
                order_goods = OrderGoods.objects.get(order=order,sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status =5   # 更新订单状态
        order.save()
        return redirect(reverse('user:order',kwargs={'page':1}))



