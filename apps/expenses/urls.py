from django.urls import path
from .views import ExpenseListView, ExpenseCreateView,ExpenseUpdateView,ExpenseDeleteView,ExpenseReportView,ExpenseReportExportExcelView
    

app_name = "expenses"

urlpatterns = [
    path("", ExpenseListView.as_view(), name="list"),
    path("create/", ExpenseCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", ExpenseUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", ExpenseDeleteView.as_view(), name="delete"),
    path("report/", ExpenseReportView.as_view(), name="report"),
    path("report/export/excel/", ExpenseReportExportExcelView.as_view(), name="report_export_excel"),
    
]