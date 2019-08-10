from django.conf.urls import url
from user.views import RegisterViews,ActiveViews,LoginViews,UserInfoViews,UserOrderViews,AddressViews,LogoutViews,DeleteViews,AddressDeleteViews,UpdateDefaultViews
from django.contrib.auth.decorators import login_required
from user import views
urlpatterns = [
    #url(r'^register$',views.register,name='register'),  # 用户注册页面
    #url(r'^register_handle$',views.register_handle,name='register_handle'),    # 用户注册处理

    url(r'^register$',RegisterViews.as_view(),name='register'),  # 用户注册以及处理
    url(r'^active/(?P<token>.*)$',ActiveViews.as_view(),name='active'),    # 用户激活

    url(r'^login$', LoginViews.as_view(), name='login'),  # 用户登入
    url(r'^logout$', LogoutViews.as_view(), name='logout'),   # 用户注销

    # url(r'^$',login_required(UserInfoViews.as_view()),name='user'),  # 用户中心-信息页
    # url(r'^order$',login_required(UserOrderViews.as_view()),name='order'),  # 用户中心-订单页
    # url(r'^address$',login_required(AddressViews.as_view()),name='address'),     # 用户中心-地址页

    url(r'^$', UserInfoViews.as_view(), name='user'),  # 用户中心-信息页
    url(r'^order/(?P<page>\d+)$', UserOrderViews.as_view(), name='order'),  # 用户中心-订单页
    url(r'^address$', AddressViews.as_view(), name='address'),  # 用户中心-地址页

    # url(r'^delete(?P<pid>\d+)$', DeleteViews.as_view(), name='delete'),  # 删除地址
url(r'^delete$', AddressDeleteViews.as_view(), name='delete'),  # 删除地址
    url(r'^update$', UpdateDefaultViews.as_view(), name='update'),    # 更新默认地址
]
