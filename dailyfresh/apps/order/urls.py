from django.conf.urls import url
from order.views import OrderPlaceViews,OrderCommitViews,OrderPayViews,CheckPayViews, CommentViews

urlpatterns = [
    url(r'^place$', OrderPlaceViews.as_view(), name='place'),    # 订单提交页面显示
    url(r'^commit$', OrderCommitViews.as_view(), name='commit'),     # 订单创建
    url(r'^pay$', OrderPayViews.as_view(), name='pay'),     # 订单支付
    url(r'^check$', CheckPayViews.as_view(), name='check'),     # 订单支付结果
    url(r'^comment/(?P<order_id>.+)$', CommentViews.as_view(), name='comment'),  # 订单评论页面
]
