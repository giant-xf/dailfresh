from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.contrib.auth import authenticate,login,logout
from django.views.generic import View
from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse,JsonResponse

from user.models import User,Address
from goods.models import GoodsSKU
from order.models import OrderGoods,OrderInfo

from celery_tasks.tasks import send_register_active_email
import re
from utils.mixin import LoginRequiredMixin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django_redis import get_redis_connection
# Create your views here.

# user/register
def register(request):
    '''注册'''
    if request.method == 'GET':
        # 显示注册页面
        # 如果是输入的地址，这是get提交
        return render(request,'register.html')

    elif request.method == 'POST':
        # 注册处理
        # 如果是表单提交，则是post提交
        # 获取数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 对数据进行校验
        if not all([username, password, email]):
            # 用户信息不全
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            # email格式不正确
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            # 用户未同意协议
            return render(request, 'register.html', {'errmsg': '用户未同意协议'})

        # 检验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在，可以注册
            user = None
        # 判断用户名是否存在
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理 ：用户注册处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        # 返回应答
        return redirect(reverse('goods:index'))

def register_handle(request):
    '''用户注册处理'''
    # 获取数据
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email  = request.POST.get('email')
    allow = request.POST.get('allow')
    # 对数据进行校验
    if not all([username,password,email]):
        # 用户信息不全
        return render(request,'register.html',{'errmsg':'数据不完整'})

    if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$',email):
        # email格式不正确
        return render(request,'register.html',{'errmsg':'邮箱格式不正确'})

    if allow != 'on':
        # 用户未同意协议
        return render(request,'register.html',{'errmsg':'用户未同意协议'})

    # 检验用户名是否重复
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # 用户名不存在，可以注册
        user = None
    # 判断用户名是否存在
    if user:
        return render(request,'register.html',{'errmsg':'用户名已存在'})

    # 进行业务处理 ：用户注册处理
    user = User.objects.create_user(username,email,password)
    user.is_active = 0
    user.save()
    # 返回应答
    return redirect(reverse('goods:index'))

# user/register
class RegisterViews(View):
    '''注册类'''
    def get(self,request):
        '''显示注册页面'''
        return render(request, 'register.html')

    def post(self,request):
        # 注册处理
        # 如果是表单提交，则是post提交
        # 获取数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 对数据进行校验
        if not all([username, password, email]):
            # 用户信息不全
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if len(username)>20or len(password)>20:
            # 账号密码多于规定位数
            return render(request, 'register.html', {'errmsg': '账号密码太长'})
        if len(username)<5or len(password)<8:
            # 账号密码小于规定位数
            return render(request, 'register.html', {'errmsg': '账号密码太短'})

        if not cpassword==password:
            # 两次密码输入不一致
            return  render(request,'register.html',{'errmsg':'两次输入的密码不一致'})

        if not re.match('^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            # email格式不正确
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            # 用户未同意协议
            return render(request, 'register.html', {'errmsg': '用户未同意协议'})

        # 检验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在，可以注册
            user = None
        # 判断用户名是否存在
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 进行业务处理 ：用户注册处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接：http://127.0.0.1:8000/user/active/id
        # 激活链接中需要包含用户的身份信息，并且把身份信息进行加密

        # 加密用户的身份信息，生成激活token
            # 第一个参数设置秘钥，第二个参数设置时间（秒）
        serializer = Serializer(settings.SECRET_KEY,3600)
        # 使用字典格式进行加密，也可以用元组，但是使用格式就需要用什么格式解密
        info = {'confirm':user.id}
        token = serializer.dumps(info)
        # 将二进制的token转换成 utf8
        token = token.decode()

        # 发送邮件
        send_register_active_email.delay(email,username,token)
        # Django自带的发邮件
        # subject = '天天生鲜欢迎信息'
        # message = ''
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>,请点击下面链接激活账户<br><a href="http:127.0.0.1:8000/user/active/%s">点击激活'%(username,token)
        # send_mail(subject,message,sender,receiver,html_message=html_message)


        # 返回应答
        return redirect(reverse('goods:index'))

# active/(?P<token>.*)
class ActiveViews(View):
    '''用户激活'''
    def get(self,request,token):
        '''进行用户激活'''
        serializer = Serializer(settings.SECRET_KEY,3600)
        try:
            info = serializer.loads(token)
            # 获取user的id
            user_id = info['confirm']
            # 查询数据库中id为user_id的对象
            user = User.objects.get(id =user_id)
            # 将激活状态设置为1
            user.is_active=1
            user.save()
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            # 激活码失效；正常情况的话企业会让用户点击链接继续发送激活码
            return HttpResponse('激活链接已失效！')

class LoginViews(View):
    '''显示登入页面'''
    def get(self,request):
        # 判断是否记住登入状态
        # if request.session.get('islogin'):
        #     return redirect(reverse('goods:index'))
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username=''
            checked=''

        # 使用模板
        return render(request,'login.html',{'username':username,'checked':checked})

    def post(self,request):
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')


        # 校验数据
        if not all([username,password]):
            return render(request,'login.html',{'errmsg':'账号密码不能为空'})

        # 业务处理：登入校验
        # 使用内置的authenticate函数校验，正确会返回一个对象，否则返回None
        user = authenticate(username=username,password=password)
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记住登入状态，使用内置的login函数
                login(request,user)

                # 获取登入后索要跳转的地址
                next_url = request.GET.get('next',reverse('goods:index'))
                # 判断是否记住账号
                remember_username = request.POST.get('remember_username')
                # 判断是否记住密码
                # remember_password = request.POST.get('remember_password')
                # 跳转到首页
                response =  redirect(next_url)
                if remember_username=='on':
                    # 记住密码功能
                    # if remember_password=='on':
                    #     request.session['islogin']=True
                    # else:
                    #     request.session['islogin']=False
                    #     del request.session['islogin']
                    response.set_cookie('username',username,max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                # 返回response
                return response


            else:
                # 账号未激活
                return render(request,'login.html',{'errmsg':'账号未激活!'})
        else:
            # user=None，返回对象为None
            return render(request,'login.html',{'errmsg':'账号或密码错误!'})

class LogoutViews(LoginRequiredMixin,View):
    '''注销登入'''
    def get(self,request):
        # Django内置注销
        # 清除用户session信息
        logout(request)

        # 跳转到首页
        return redirect(reverse('goods:index'))

class UserInfoViews(LoginRequiredMixin,View):
    '''用户中心-信息页'''
    def get(self,request):
        # 显示
        # 传递page参数代表用户所点的当前页，显示当前字颜色
        # request.user
        # 如果用户未登入 ->user返回AnonymousUser类对象实例
        # 如果用户登入 -> user返回User对象实例
        # 都有is_authenticated()方法，
        # request.user.is_authenticated()返回User对象，反之为空
        #除了自己传给模板文件传递的变量之外，Django也会把request.user传给模板文件

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的浏览记录
        # redis与python互动连接操作redis方法
        # from redis import StrictRedis
        # sr = StrictRedis(host='192.168.1.103',port='6379',db=9)
        con = get_redis_connection('default')
        history_key = 'history_%s'%user.id

        # 获取用户最新5个商品的id
        # sku_ids是一个列表
        sku_ids = con.lrange(history_key, 0, 4)
        # 从数据库中查询用户浏览商品的具体信息

        # 第一种方式
        # # 查询出来的good_li查询集是按照id排序的
        # good_li = GoodsSKU.objects.filter(id__in=sku_ids)
        # # 对数据进行还原顺序
        # goods_res=[]
        # for id in sku_ids:
        #     for good in good_li:
        #         if id==good.id:
        #             goods_res.append(good)

        # 第二种方式
        # 根据sku_ids的值查询
        goods_res=[]
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_res.append(goods)

        # 组织上下文
        context = {'page':'user','address':address,'goods_res':goods_res}
        return render(request,'user_center_info.html',context)

class UserOrderViews(LoginRequiredMixin,View):
    '''用户中心-订单页'''
    def get(self, request, page):
        # 获取用户的全部订单
        user = request.user
        # 查询所有订单
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历订单，获取所有商品
        for order in orders:
            # 根据order_id查询订单中所有商品
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)
            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算商品的小计
                amount = order_sku.count*order_sku.price
                # 动态的给order_sku添加amount属性，保存订单商品的小计
                order_sku.amount = amount
            # 动态的给order增加属性，保存订单状态
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态的给order增加属性，保存订单商品的信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders,2)

        # 设置page页码的类容
        try:
            page = int(page)
        except Exception as e:
            # 页码输入不符合要求
            page = 1
        if page > paginator.num_pages:
            # page页码大于总页码时
            page = 1
        # 获取第page页的Page的实例对象
        order_page = paginator.page(page)

        # todo：进行页码控制，页面上最多显示5页
        # 1.总页数小于5页，页面上显示所有页数
        # 2.如果当前页是前三页，显示1-5
        # 3.如果当前页是后三页，显示后5页
        # 4.其他情况，显示当前页前两页、当前页、和当前页后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif page >= num_pages - 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        context = {'order_page':order_page,
                   'pages':pages,
                   'page': 'order'}

        return render(request, 'user_center_order.html',context)

# /address
class AddressViews(LoginRequiredMixin,View):
    '''用户中心-地址页'''
    def get(self, request):

        # 获取用户的当前默认收货地址
        # 获取用户登入的User对象
        user = request.user
        # 获取用户默认收货地址
        try:
            address = Address.objects.filter(user=user)
            checked = 'checked'
        except Address.DoesNotExist:
            # 不存在默认收货地址
            address = None
            checked = ''

        # 组织上下文
        context = {'page': 'address','address':address,'checked':checked}
        # 使用模板
        return render(request, 'user_center_site.html', context)

    def post(self, request):
        '''添加收货地址'''
        # 接受数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 进行数据校验
        # 校验数据填写是否完整
        if not all([receiver,addr,phone]):
            return render(request,'user_center_site.html',{'errmsg':'数据填写不完整'})
        # 校验手机号
        if not re.match(r'1[3|4|5|6|7|8|9][0-9]{9}$',phone):
            return render(request,'user_center_site.html',{'errmsg': '手机号码格式不正确'})

        # 业务处理：添加收货地址
        # 如果用户已经存在默认地址，则添加地址不作为默认地址，否则作为默认地址
        # 获取User对象实例
        user = request.user
        # try:
        #     address = Address.objects.get(user=user,is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        address = Address.objects.get_default_address(user)

        if address:
            is_default=False
        else:
            is_default=True

        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)
        # 返回应答,刷新地址页面
        return redirect(reverse('user:address'))    # get请求方式

# url传参,删除地址
# /delete/id
class DeleteViews(LoginRequiredMixin,View):
    '''删除地址'''
    def get(self,request,pid):
        # 获取User对象
        user = request.user
        # 查找对象的对应的地址信息
        address = Address.objects.get(user=user, id=pid)
        # 删除对应的地址信息
        address.delete()
        return redirect(reverse('user:address'))

# 采用ajax  post请求
# 需要传入的参数：地址信息id(address_id)
class AddressDeleteViews(View):
    '''删除地址'''
    def post(self,request):
        '''删除地址'''
        # 获取User对象
        user = request.user
        # 判断用户登入状态
        if not user.is_authenticated():
            return JsonResponse({'res':1, 'errmsg':'用户未登入'})
        # 获取数据
        address_id = request.POST.get('address_id')
        # 数据校验
        if not address_id:
            return JsonResponse({'res': 2, 'errmsg': '数据不完整'})
        # 校验地址是否存在
        try:
            address = Address.objects.get(user=user,id=address_id)
        except Address.DoesNotExist:
            # 数据不存在
            return JsonResponse({'res': 3, 'errmsg': '不存在该地址'})
        # 业务处理：删除地址
        address.delete()
        return  JsonResponse({'res': 4, 'message': '删除成功'})

# 采用ajax，post请求
# 前端需要传递的参数：地址id(address_id)
# /update
class UpdateDefaultViews(View):
    '''更新默认地址'''
    def post(self,request):
        # 获取User对象
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 2, 'errmsg': '用户未登入'})
        # 获取数据
        address_id = request.POST.get('address_id')

        # 数据校验
        if not address_id:
            return JsonResponse({'res':3, 'errmsg':'无效的地址id'})
        # 判断是否是默认地址
        addr = Address.objects.get(user=user, id=address_id)
        if addr.is_default:
            # 是默认地址
            return JsonResponse({'res':4, 'errmsg':'修改失败'})

        # 业务处理:更新默认地址
        # 将所有地址变成非默认
        address = Address.objects.filter(user=user)
        for addr in address:
            addr.is_default=False
            addr.save()
        # 查找对象的对应的地址信息
        addr = Address.objects.get(user=user, id=address_id)
        # 更新address的default的值
        addr.is_default=True
        addr.save()
        return JsonResponse({'res':1, 'message':'修改成功'})



