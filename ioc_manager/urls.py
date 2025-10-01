from django.urls import path
from .views import IndexView, ValidateUploadView, LoadNewIocsView, IocListView, ExportIngestedTxtView, ExportNotIngestedTxtView, ChangeIocStateView, AuditCreateView, PurgeApiView, BulkChangeStateView
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('api/validate-upload/', ValidateUploadView.as_view(), name='validate_upload'),
    path('api/load-new/', LoadNewIocsView.as_view(), name='load_new'),
    path('api/iocs/', IocListView.as_view(), name='iocs_list'),
    path('api/export/ingested/', ExportIngestedTxtView.as_view(), name='export_ingested'),
    path('api/export/not-ingested/', ExportNotIngestedTxtView.as_view(), name='export_not_ingested'),
    path('api/change-state/', ChangeIocStateView.as_view(), name='change_state'),
    path('api/audit/create/', AuditCreateView.as_view(), name='audit_create'),
    path('api/purge/', PurgeApiView.as_view(), name='purge_api'),
    path('iocs/bulk_change_state/', BulkChangeStateView.as_view(), name='bulk_change_state'),
]
