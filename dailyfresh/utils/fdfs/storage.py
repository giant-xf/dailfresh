from django.core.files.storage import Storage
from fdfs_client.client import  Fdfs_client
from django.conf import settings
class FDFSStorage(Storage):
    ''' fast  dfs文件存储类'''
    def __init__(self,client_conf=None, base_url=None):
        '''初始化'''
        # 初始化配置
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf
        if base_url is None:
            base_url = settings.FDFS_BASE_URL
        self.base_url = base_url

    def _open(self, name , mode='rb'):
        '''打开文件时使用'''
        pass

    def _save(self,name,content):
        '''保存文件时使用'''
        # name:你选择上传文件的名字
        # content:包含上传文件时的File对象

        # 创建一个Fdfs_client对象
        client = Fdfs_client(self.client_conf)

        # 上传文件到Fast  dfs系统中
        res = client.upload_by_buffer(content.read())

        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }

        if res.get('Status')!= 'Upload successed.':
            # 上传失败
            raise Exception('文件上传失败')

        # 在image表中保存/group1/...  内容，返回的Remote file_id是这部分类容
        # 获取返回的文件id
        filename = res.get('Remote file_id')

        return filename

    # 调用_save方法之前会调用exist方法
    def exists(self, name):
        '''Django判断文件名字是否可用'''
        # 文件保存在Fdfs上面，不保存在Django上面，直接返回false就行了
        return  False

    def url(self,name):
        '''返回访问文件的炉具'''
        return self.base_url+name




