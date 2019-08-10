from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection
# Create your views here.
# 添加商品到购物车：
# 1)请求方式，采用ajax：post
# 如果涉及到数据的修改(增删改)，则采用post
# 只涉及到数据的传递，则采用get
# 2)传递参数：商品id(sku_id), 商品数量(count)

# ajax请求都在后台，所以不能继承utils中的LoginRequiredMixin()，页面不会跳转，
# ajax中post请求也需要csrf_token;将csrf_token放在某个input提交中提交过来
# /cart/add
class CartAddViews(View):
    '''购物车记录添加商品'''
    def post(self,request):
        '''购物车添加记录'''
        # 先判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            # 用户未登录
            return JsonResponse({'res':0,'errmsg':'请先登入'})
        # 1.接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 2.进行数据校验
        # 2.1第一步校验：数据完整性
        if not all([sku_id,count]):
            # 数据不完整
            return JsonResponse({'res':1, 'errmsg':'数据不完整'})
        # 2.2第二步校验：用户添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数据不合法
            return JsonResponse({'res':2,'errmsg':'商品数目出错'})
        # 2.3第三步校验：商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res':3, 'errmsg': '商品不存在'})
        # 3.业务处理：进行购物车数据添加
        # 获取redis中的数据
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # 先尝试获取数据库中的sku_id的数量-->hget(cart_key,属性)
        # 如果sku_id在hash中不存在值，hget返回None
        cart_count = conn.hget(cart_key,sku_id)
        if cart_count:
            # 如果有值,累加购物车中的数量
            count += int(cart_count)
        # 判断加入购物车中的数量是否大于库存
        if count > sku.stock:
            return JsonResponse({'res':4,'errmsg':'商品的库存不足'})

        # 设置hash中的sku_id对应的值，hash中不存在的值，hset相当于新增
        conn.hset(cart_key,sku_id,count)

        # 计算用户购物车中的条目数
        total_count = conn.hlen(cart_key)
        # 4.返回应答
        return JsonResponse({'res':5,'total_count':total_count,'errmsg':'加入购物车成功'})

# /cart
class CartInfoViews(LoginRequiredMixin,View):
    '''购物车页面'''
    def get(self,request):
        '''显示购物车页面'''
        # 获取登入的用户
        user = request.user
        # 获取用户购物车中的信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # {'商品id':商品数量}
        cart_dict = conn.hgetall(cart_key)

        # 定义一个空列表存放增加属性了的商品sku对象
        skus=[]
        # 保存用户购物车中的商品总件数和商品总价数
        total_count = 0
        total_price = 0
        # 遍历字典中的键和值
        for sku_id, count in cart_dict.items():
            # print(sku_id,count)
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取商品单价
            price = sku.price
            # 单个商品小计
            amount = price*int(count)
            # 动态的给对象增加属性
            sku.count = count
            sku.amount = amount
            # 将对象加入列表中
            skus.append(sku)
            # 商品总件数和总价
            total_count +=int(count)
            total_price +=amount
        # 组织上下文
        context = {'total_count':total_count,
                   'total_price':total_price,
                   'skus':skus}
        return render(request,'cart.html',context)

# 更新购物车记录
# 采用ajax  post请求
# 前端需要传过来的参数：商品id(sku_id), 更新商品数量(count)
# /cart/update
class CartUpdateViews(View):
    '''购物车记录更新'''
    def post(self,request):
        '''购物车记录更新'''
        # 获取用户
        user = request.user
        if not user.is_authenticated():
            # 用户未登入
            return JsonResponse({'res': 0, 'errmsg':'用户未登入'})
        # 1.接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 2.进行数据校验
        # 2.1第一步校验：数据完整性
        if not all([sku_id, count]):
            # 数据不完整
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 2.2第二步校验：用户添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数据不合法
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 2.3第三步校验：商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        # 3.业务处理：进行购物车数据添加
        # 获取redis中的数据
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # 判断加入购物车中的数量是否大于库存
        if count > sku.stock:
            return JsonResponse({'res':4,'errmsg':'商品的库存不足'})
        # 更新数据库中的数量
        conn.hset(cart_key, sku_id, count)
         # {'商品id':商品数量}
        total_count = 0
        # 求购物车商品总数量 方法一
        cart_dict = conn.hgetall(cart_key)
        for count in cart_dict.values():
            total_count +=int(count)
        # 求购物车商品总数量 方法二
        # vals = conn.hvals(cart_key)
        # for count in vals:
        #     total_count +=int(count)
        # 返回应答
        return JsonResponse({'res':5, 'total_count':total_count, 'message': '更新成功'})

# 删除购物车数据
# 采用ajax  post请求
# 前端需要传过来的参数：商品id(sku_id),
# /cart/delete
class CartDeleteViews(View):
    '''删除购物车数据'''
    def post(self,request):
        '''购物车记录数据'''
        user = request.user
        if not user.is_authenticated():
            # 用户未登入
            return JsonResponse({'res':1, 'errmsg':'用户未登入'})

        # 获取数据
        sku_id = request.POST.get('sku_id')

        # 数据校验
        if not sku_id:
            return JsonResponse({'res': 2, 'errmsg': '无效商品id'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理：购物车记录删除
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id

        # 删除数据
        conn.hdel(cart_key, sku_id)
        # 求购物车商品总数量
        total_count = 0
        vals = conn.hvals(cart_key)
        for count in vals:
            total_count +=int(count)
        # 返回应答
        return JsonResponse({'res': 4,'total_count':total_count, 'message': '删除成功'})


