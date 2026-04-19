from django.urls import path
from .views import (
    ExpenseAddHTML, ExpenseListHTML, ExpenseDetailHTML
)

urlpatterns = [

    # HTML Template Pages
    path('add/', ExpenseAddHTML.as_view(), name='expense-add-html'),
    path('list/', ExpenseListHTML.as_view(), name='expense-list-html'),
    path('<int:pk>/view/', ExpenseDetailHTML.as_view(), name='expense-detail-html'),

]
