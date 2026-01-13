# urls.py - Cleaned Version
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from .views import (
    IndexView, 
    ValidateUploadView, 
    LoadNewIocsView, 
    IocListView, 
    ExportIngestedTxtView, 
    ExportNotIngestedTxtView, 
    AuditCreateView, 
    PurgeApiView, 
    BulkChangeStateView, 
    GenerarReporteView, 
    IocBulkSearchView, 
    ValidateAndIngestView, 
    ExportIngestedByBatchView, 
    ChangeIocStateView,
    ExportClassifiedView,
    logout_view, 
    login_view,
)

urlpatterns = [
    # Auth
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('api-token-auth/', obtain_auth_token, name='api_token_auth'),
    
    # UI
    path('', IndexView.as_view(), name='index'),

    # API
    path('api/validate-upload/', ValidateUploadView.as_view(), name='validate_upload'),
    path('api/load-new/', LoadNewIocsView.as_view(), name='load_new'),
    path('api/iocs/', IocListView.as_view(), name='iocs_list'),
    path('api/export/ingested/', ExportIngestedTxtView.as_view(), name='export_ingested'),
    path('api/export/not-ingested/', ExportNotIngestedTxtView.as_view(), name='export_not_ingested'),
    path('api/export/classified/', ExportClassifiedView.as_view(), name='export_classified'),
    
    path('api/audit/create/', AuditCreateView.as_view(), name='audit_create'),
    path('api/purge/', PurgeApiView.as_view(), name='purge_api'),

    
    path('iocs/bulk_change_state/', BulkChangeStateView.as_view(), name='bulk_change_state'),
    
    path('api/reportes/', GenerarReporteView.as_view(), name='api_reportes'),
    path("api/iocs/bulk-search/", IocBulkSearchView.as_view()),
    path('api/iocs/validate-ingest/', ValidateAndIngestView.as_view()),
    
    # Single Item Routes
    path('api/change-state/<int:pk>/', ChangeIocStateView.as_view(), name='change_state_single'),
    path('api/change-state/', ChangeIocStateView.as_view(), name='change_state_payload'),
    path('api/purge/<int:pk>/', PurgeApiView.as_view(), name='purge_api_single'),
    
    path('export/ingested-by-batch/<str:batch_id>/', ExportIngestedByBatchView.as_view()),
]
