from django.conf.urls import url
from cart.views import CartAddViews,CartInfoViews,CartUpdateViews,CartDeleteViews
urlpatterns = [
    url(r'^add$',CartAddViews.as_view(), name='add'),   # 购物车添加商品
    url(r'^$',CartInfoViews.as_view(), name='show'),    # 购物车页面显示
    url(r'^update$',CartUpdateViews.as_view(), name='update'),  # 购物车记录更新
    url(r'^delete$',CartDeleteViews.as_view(), name='delete'),  # 购物车记录删除

]
