from django.shortcuts import render,redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.core.cache import cache
from django.core.paginator import Paginator
from goods.models import *
from order.models import OrderGoods
from django_redis import get_redis_connection
# Create your views here.

# 127.0.0.1:8000/index
class IndexViews(View):
    '''首页'''
    def get(self,request):
        '''显示首页'''
        # 尝试获取缓存中的数据
        context = cache.get('index_page_data')
        if context is None:
            print('设置缓存')
        # 缓冲中没有数据
            # 获取商品的种类信息
            types = GoodsType.objects.all()

            # 获取首页轮播商品信息,    order_by默认升序
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')

            # 获取首页促销商品信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            # 获取首页分类商品展示信息
            for type in types:  # GoodsType
                # 获取type种类首页分类商品图片展示信息
                image_banner = IndexTypeGoodsBanner.objects.filter(type=type,display_type=1).order_by('index')
                # 获取type种类首页分类商品文字展示信息
                title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
                # 动态给type增加属性，分别保存首页分类商品的图片展示信息和文字展示信息
                type.image_banners = image_banner
                type.title_banners = title_banner

            # 组织模板上下文
            context = {'types': types,
                       'goods_banners': goods_banners,
                       'promotion_banners': promotion_banners}
            # 设置缓存
            # key  values  timeout
            cache.set('index_page_data',context,3600)

        # 获取购物车中的商品数量
        # 设计保存形式：hash保存；cart_用户id:{'sku_id1':数量,'sku_id2':数量}
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登入
            # 拿到redis数据库中的链接
            conn = get_redis_connection('default')
            # 拼接出key值
            cart_key = 'cart_%d'%user.id
            # 使用hlen获取属性值的个数
            cart_count = conn.hlen(cart_key)


        context.update(cart_count=cart_count)

        # 使用模板
        return render(request,'index.html',context)

# /goods/商品id
class DetailViews(View):
    '''详情页'''
    def get(self,request,goods_id):
        '''显示详情页'''
        # 查找商品sku
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))

        # 获取商品种类信息
        types = GoodsType.objects.all()

        # 获取商品评论
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).exclude(id=goods_id).order_by('-create_time')[:2]

        # 获取同一个SPU下的不同规格的商品
        same_spu_sku = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取购物车中的商品数量
        # 设计保存形式：hash保存；cart_用户id:{'sku_id1':数量,'sku_id2':数量}
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登入
            # 拿到redis数据库中的链接
            conn = get_redis_connection('default')
            # 拼接出key值
            cart_key = 'cart_%d' % user.id
            # 使用hlen获取属性值的个数
            cart_count = conn.hlen(cart_key)

            # 添加用户浏览记录
            conn = get_redis_connection('default')
            # 拼接出key值
            history_key = 'history_%d'% user.id
            # 移除里面有的相同记录
            conn.lrem(history_key,0,goods_id)
            # 从左侧添加数据[3,2,1]
            conn.lpush(history_key,goods_id)
            # 只保留五条数据，进行裁剪
            conn.ltrim(history_key,0,4)

        context = {'sku':sku, 'types':types,
                   'sku_orders':sku_orders,
                   'new_skus':new_skus,
                   'same_spu_sku':same_spu_sku,
                   'cart_count':cart_count}

        return render(request,'detail.html',context)

# /list?type_id=种类id&page=页码&sort=排序方式
# /list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式
class ListViews(View):
    '''列表页'''
    def get(self,request, type_id, page):
        '''显示列表页'''
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 种类id不存在
            return redirect(reverse('goods:index'))

        # 获取商品分类信息信息
        types = GoodsType.objects.all()

        # 获取排列方式
        # sort=default 按照默认id排序
        # sort=price 按照价格排序
        # sort=hot 按照人气排序
        # 获取需要排序的sku信息
        sort = request.GET.get('sort')
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对数据进行分页
        # 后面参数表示每页显示的个数
        paginator = Paginator(skus,5)

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
        skus_page = paginator.page(page)

        # todo：进行页码控制，页面上最多显示5页
        # 1.总页数小于5页，页面上显示所有页数
        # 2.如果当前页是前三页，显示1-5
        # 3.如果当前页是后三页，显示后5页
        # 4.其他情况，显示当前页前两页、当前页、和当前页后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1,num_pages+1)
        elif page <=3:
            pages = range(1,6)
        elif page >= num_pages-2:
            pages = range(num_pages-4,num_pages+1)
        else:
            pages = range(page-2,page+3)


        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取购物车中商品数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登入
            # 拿到redis数据库中的链接
            conn = get_redis_connection('default')
            # 拼接出key值
            cart_key = 'cart_%d' % user.id
            # 使用hlen获取属性值的个数
            cart_count = conn.hlen(cart_key)

        context = {'type':type,'types':types,
                   'skus_page':skus_page,
                   'new_skus':new_skus,
                   'cart_count':cart_count,
                   'pages':pages,
                   'sort':sort}
        # 使用模板
        return render(request,'list.html',context)



