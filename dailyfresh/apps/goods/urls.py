from django.conf.urls import url
from goods.views import IndexViews, DetailViews, ListViews

urlpatterns = [
    url(r'^index$',IndexViews.as_view(),name='index'),     # 显示首页
    url(r'^goods/(?P<goods_id>\d+)$',DetailViews.as_view(),name='detail'),    # 显示详情页
    url(r'^list/(?P<type_id>\d+)/(?P<page>\d+)$', ListViews.as_view(),name='list'),  # 显示列表页
]
