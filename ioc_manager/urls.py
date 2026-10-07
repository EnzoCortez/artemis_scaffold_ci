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
    # AuditCreateView removed
    PurgeApiView, 
    BulkChangeStateView, 
    GenerarReporteView, 
    ReportesTotalesHerramientasView,
    ReportesAnalisisTxtView,
    IocBulkSearchView, 
    ValidateAndIngestView, 
    ExportIngestedByBatchView, 
    ChangeIocStateView,
    ExportClassifiedView,
    ExportCsvStrategyView,
    logout_view, 
    login_view,
)
from .views_maintenance import DBLogSizeView, DBLogShrinkView, DashboardStatsView, UploadHistoryView
from .views_tool_load import ValidateToolInitialLoadView, ExecuteToolInitialLoadView

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
    path('api/export/csv/', ExportCsvStrategyView.as_view(), name='export_csv'),
    
    # Tool specific load
    path('api/tool-initial-load/validate/', ValidateToolInitialLoadView.as_view(), name='validate_tool_load'),
    path('api/tool-initial-load/execute/', ExecuteToolInitialLoadView.as_view(), name='execute_tool_load'),
    
    # Audit/Purge
    # path('api/audit/create/': AuditCreateView removed)
    path('api/purge/', PurgeApiView.as_view(), name='purge_api'),

    
    path('iocs/bulk_change_state/', BulkChangeStateView.as_view(), name='bulk_change_state'),
    
    path('api/reportes/', GenerarReporteView.as_view(), name='api_reportes'),
    path('api/reportes/totales-herramientas/', ReportesTotalesHerramientasView.as_view()),
    path('api/reportes/analisis-txt/', ReportesAnalisisTxtView.as_view()),
    path("api/iocs/bulk-search/", IocBulkSearchView.as_view()),
    path('api/iocs/validate-ingest/', ValidateAndIngestView.as_view()),
    path('api/iocs/assign-tool-manual/', views.AssignToolManualView.as_view()),
    path('api/iocs/assign-tool-bulk/', views.AssignToolBulkView.as_view()),
    
    # Single Item Routes
    path('api/change-state/<int:pk>/', ChangeIocStateView.as_view(), name='change_state_single'),
    path('api/change-state/', ChangeIocStateView.as_view(), name='change_state_payload'),
    path('api/purge/<int:pk>/', PurgeApiView.as_view(), name='purge_api_single'),
    
    
    path('export/ingested-by-batch/<str:batch_id>/', ExportIngestedByBatchView.as_view()),
    
    # Maintenance & Stats
    path('api/stats/dashboard/', DashboardStatsView.as_view(), name='dashboard_stats'),
    path('api/maintenance/db-log-size/', DBLogSizeView.as_view(), name='db_log_size'),
    path('api/maintenance/db-log-shrink/', DBLogShrinkView.as_view(), name='db_log_shrink'),
    path('api/stats/upload-history/', UploadHistoryView.as_view(), name='upload_history'),
]
