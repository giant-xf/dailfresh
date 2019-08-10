from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
import time
from django.template import loader,RequestContext


#不运行Django环境时需要初始化，
import os
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()

from goods.models import *


# 我们这里案例使用redis作为broker
# 第一个参数是名字,redis数据库，数据库ip，端口，数据库号
app = Celery('celery_tasks.tasks', broker='redis://192.168.1.103:6379/8')

# 定义函数任务
@app.task
def send_register_active_email(to_email,username,token):
    '''发送激活邮件'''
    # 组织邮件信息
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>,请点击下面链接激活账户<br><a href="http:127.0.0.1:8000/user/active/%s">点击激活' % (
    username, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)
    time.sleep(5)

@app.task
def generate_static_index_html():
    '''产生静态文件页面'''
    # 获取商品的种类信息
    types = GoodsType.objects.all()

    # 获取首页轮播商品信息,    order_by默认升序
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 获取首页促销商品信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取首页分类商品展示信息
    for type in types:  # GoodsType
        # 获取type种类首页分类商品图片展示信息
        image_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
        # 获取type种类首页分类商品文字展示信息
        title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
        # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
        type.image_banners = image_banner
        type.title_banners = title_banner


    # 组织模板上下文
    context = {'types': types,
               'goods_banners': goods_banners,
               'promotion_banners': promotion_banners}

    # 使用模板
    # 1.加载模板文件,返回模板对象
    temp = loader.get_template('static_index.html')
    # # 2.定义模板上下文
    # context = RequestContext(request, context)
    # 3.模板渲染
    static_index_html = temp.render(context)

    # 生成首页对应的静态页面
    save_path = os.path.join(settings.BASE_DIR,'static/index.html')

    # 创建文件
    with open(save_path,'w') as f:
         # 将static_index_html内容写入index.html文件中
        f.write(static_index_html)

