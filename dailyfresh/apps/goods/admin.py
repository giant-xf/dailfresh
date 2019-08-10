from django.contrib import admin
from django.core.cache import cache
from goods.models import *
# Register your models here.

class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        '''新增或更新表中的数据时调用'''
        super().save_model(request,obj,form,change)

        # 发出任务， 让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        '''删除表中的数据时调用'''
        super().delete_model(request,obj)

        # 发出任务， 让celery worker重新生成首页静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页缓存
        cache.delete('index_page_data')

class IndexPromotionBannerAdmin(BaseModelAdmin):
    '''首页促销活动模型类'''
    list_display = ['name', 'url','image','index']

class IndexGoodsBannerAdmin(BaseModelAdmin):
    '''首页轮播商品展示模型类'''
    list_display = ['sku', 'image','index']

class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    '''首页分类商品展示模型类'''
    list_display = ['type','sku','display_type','index']

class GoodSKUAdmin(BaseModelAdmin):
    '''商品SKU模型类'''
    list_display = ['type', 'goods','name','desc','price','unite','image','stock','sales','status']

class GoodsTypeAdmin(BaseModelAdmin):
    '''商品类型模型类'''
    pass

class GoodsAdmin(BaseModelAdmin):
    '''商品SPU模型类'''
    list_display = ['name','detail']

class GoodsImageAdmin(BaseModelAdmin):
    '''商品图片模型类'''
    list_display = ['sku', 'image']


admin.site.register(IndexPromotionBanner,IndexPromotionBannerAdmin)
admin.site.register(IndexGoodsBanner,IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner,IndexTypeGoodsBannerAdmin)
admin.site.register(GoodsSKU,GoodSKUAdmin)
admin.site.register(GoodsType,GoodsTypeAdmin)
admin.site.register(Goods,GoodsAdmin)
admin.site.register(GoodsImage,GoodsImageAdmin)
