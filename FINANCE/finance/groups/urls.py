from django.urls import path
from .views import (
    GroupCreateHTML, GroupListHTML, GroupDetailHTML,
    AddMemberHTML, AddGroupExpenseHTML, GroupInviteRespondHTML,
    GroupSpaceHTML, GroupMessageListAPI, GroupMessageCreateAPI,
    CreateExpenseAPI, GenerateSplitSuggestionAPI, FinalizeSplitAPI,
    SearchUsersAPI, InviteUserAPI, InviteRespondAPI
)

urlpatterns = [

    # HTML ROUTES
    path('create/', GroupCreateHTML.as_view(), name='group-create-html'),
    path('list/', GroupListHTML.as_view(), name='group-list-html'),
    path('<int:pk>/view/', GroupDetailHTML.as_view(), name='group-detail-html'),
    path('<int:pk>/space/', GroupSpaceHTML.as_view(), name='group-space-html'),
    path('add-member/', AddMemberHTML.as_view(), name='group-add-member-html'),
    path('invite/<int:pk>/respond/', GroupInviteRespondHTML.as_view(), name='group-invite-respond-html'),
    path('add-expense/', AddGroupExpenseHTML.as_view(), name='group-add-expense-html'),

    # API ROUTES - Messages
    path('api/messages/', GroupMessageListAPI.as_view(), name='api-messages-list'),
    path('api/messages/create/', GroupMessageCreateAPI.as_view(), name='api-messages-create'),

    # API ROUTES - Splits
    path('api/create-expense/', CreateExpenseAPI.as_view(), name='api-create-expense'),
    path('api/generate-split-suggestion/', GenerateSplitSuggestionAPI.as_view(), name='api-generate-split'),
    path('api/finalize-split/', FinalizeSplitAPI.as_view(), name='api-finalize-split'),

    # API ROUTES - Existing
    path('api/search-users/', SearchUsersAPI.as_view(), name='api-search-users'),
    path('api/invite-user/', InviteUserAPI.as_view(), name='api-invite-user'),
    path('api/invite/<int:pk>/respond/', InviteRespondAPI.as_view(), name='api-invite-respond'),

]

