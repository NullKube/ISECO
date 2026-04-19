from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer

from .models import Group, GroupMember, GroupExpense, GroupInvite, GroupMessage, ExpenseSplit, SplitAnalysis
from .serializers import GroupMessageSerializer, ExpenseSplitSerializer
from users.models import User
from notifications.models import Notification
from ai_engine.split_analyzer import suggest_split, auto_rebalance_split


class GroupCreateHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "create_group.html"

    def get(self, request):
        return Response()

    def post(self, request):
        name = request.data.get("name")
        created_by = request.data.get("created_by")

        user = get_object_or_404(User, pk=created_by)
        group = Group.objects.create(name=name, created_by=user)

        # Automatically add creator as a member of the group
        GroupMember.objects.create(group=group, user=user)

        return Response({
            "message": "Group created successfully",
            "group": group,
        })


class GroupListHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "group_list.html"

    def get(self, request):
        groups = Group.objects.all()
        return Response({"groups": groups})


class GroupDetailHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "group_detail.html"

    def get(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        members = group.members.all()
        expenses = group.expenses.all()
        invites = group.invites.filter(status="pending")
        return Response({
            "group": group,
            "members": members,
            "expenses": expenses,
            "invites": invites,
            "current_user": request.user,
        })


class GroupSpaceHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "group_space.html"

    def get(self, request, pk):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "You must be logged in to access this group space"}, status=403)

        group = get_object_or_404(Group, pk=pk)

        # Check if user is a member
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return Response({"error": "You are not a member of this group"}, status=403)

        messages = group.messages.all().order_by('created_at')[:50]
        members = group.members.all()
        latest_expense = group.expenses.latest('created_at') if group.expenses.exists() else None

        return Response({
            "group": group,
            "messages": GroupMessageSerializer(messages, many=True).data,
            "members": members,
            "current_user": request.user,
            "latest_expense": latest_expense,
        })


class GroupMessageListAPI(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        group_id = request.GET.get("group_id")
        limit = int(request.GET.get("limit", 50))
        offset = int(request.GET.get("offset", 0))

        if not group_id:
            return Response({"error": "group_id required"}, status=400)

        group = get_object_or_404(Group, pk=group_id)

        # Check membership
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return Response({"error": "Not a member of this group"}, status=403)

        messages = group.messages.all().order_by('-created_at')[offset:offset+limit]

        return Response({
            "messages": GroupMessageSerializer(messages, many=True).data,
            "total_count": group.messages.count(),
        })


class GroupMessageCreateAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        group_id = request.data.get("group_id")
        message_text = request.data.get("message", "").strip()

        if not group_id or not message_text:
            return Response({"error": "group_id and message required"}, status=400)

        group = get_object_or_404(Group, pk=group_id)

        # Check membership
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return Response({"error": "Not a member of this group"}, status=403)

        message = GroupMessage.objects.create(
            group=group,
            sender=request.user,
            message=message_text
        )

        return Response({
            "success": True,
            "message": GroupMessageSerializer(message).data,
        })


class CreateExpenseAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        group_id = request.data.get("group_id")
        amount = request.data.get("amount")
        description = request.data.get("description")

        if not group_id or not amount or not description:
            return Response({"error": "group_id, amount, and description required"}, status=400)

        try:
            group = Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            return Response({"error": "Group not found"}, status=404)

        # Check membership
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return Response({"error": "Not a member of this group"}, status=403)

        # Create the expense
        expense = GroupExpense.objects.create(
            group=group,
            user=request.user,
            amount=amount,
            description=description,
            date=timezone.now().date()
        )

        return Response({
            "success": True,
            "expense": {
                "id": expense.id,
                "group_id": group.id,
                "amount": expense.amount,
                "description": expense.description,
            }
        })


class GenerateSplitSuggestionAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        expense_id = request.data.get("expense_id")
        group_id = request.data.get("group_id")

        if not expense_id or not group_id:
            return Response({"error": "expense_id and group_id required"}, status=400)

        try:
            expense = GroupExpense.objects.get(pk=expense_id)
            group = Group.objects.get(pk=group_id)
        except (GroupExpense.DoesNotExist, Group.DoesNotExist):
            return Response({"error": "Expense or group not found"}, status=404)

        # Check membership
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            return Response({"error": "Not a member of this group"}, status=403)

        # Generate suggestions using AI engine
        result = suggest_split(group, expense)

        if not result.get('success'):
            return Response({"error": result.get('message', 'Failed to generate suggestions')}, status=400)

        # Save analysis data
        analysis = SplitAnalysis.objects.create(
            group=group,
            expense=expense,
            analysis_data=result['analysis_data'],
            algorithm_version=result['algorithm_version']
        )

        return Response({
            "success": True,
            "expense": result['expense'],
            "splits": result['splits'],
            "total": result['total'],
            "analysis_id": analysis.id,
        })


class FinalizeSplitAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        expense_id = request.data.get("expense_id")
        adjustments = request.data.get("adjustments", {})  # {user_id: final_amount}

        if not expense_id or not adjustments:
            return Response({"error": "expense_id and adjustments required"}, status=400)

        try:
            expense = GroupExpense.objects.get(pk=expense_id)
        except GroupExpense.DoesNotExist:
            return Response({"error": "Expense not found"}, status=404)

        # Check membership
        if not GroupMember.objects.filter(group=expense.group, user=request.user).exists():
            return Response({"error": "Not a member of this group"}, status=403)

        # Verify total matches
        total = sum(float(v) for v in adjustments.values())
        if abs(total - expense.amount) > 0.01:
            return Response({
                "error": f"Total adjustments (₹{total}) don't match expense amount (₹{expense.amount})",
                "submitted_total": total,
                "expected_total": expense.amount,
            }, status=400)

        # Create/update splits
        splits_created = []
        for user_id, final_amount in adjustments.items():
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                continue

            split, created = ExpenseSplit.objects.get_or_create(
                expense=expense,
                user=user,
                defaults={
                    'suggested_amount': final_amount,
                    'adjusted_amount': final_amount,
                    'final_amount': final_amount,
                    'status': 'accepted'
                }
            )

            if not created:
                split.adjusted_amount = final_amount
                split.final_amount = final_amount
                split.status = 'accepted'
                split.save()

            splits_created.append({
                "user_id": user.id,
                "username": user.username,
                "final_amount": final_amount,
                "status": split.status,
            })

            # Notify user about the split
            if user.id != request.user.id:
                Notification.objects.create(
                    user=user,
                    message=f"{request.user.username} added you to expense split: ₹{final_amount} for '{expense.description}' in {expense.group.name}",
                    link=f"/groups/{expense.group.id}/space/",
                )

        return Response({
            "success": True,
            "message": "Split saved and members notified",
            "settlement": {
                "expense_id": expense.id,
                "splits": splits_created,
                "total": expense.amount,
            }
        })


class AddMemberHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "add_member.html"

    def get(self, request):
        query = request.GET.get("q", "")
        group_id = request.GET.get("group", "")
        sender_id = request.GET.get("sender", "")
        users = []

        if query:
            users = User.objects.filter(username__icontains=query).order_by("username")
            if group_id:
                users = users.exclude(
                    pk__in=GroupMember.objects.filter(group_id=group_id).values_list("user_id", flat=True)
                )

        return Response({
            "users": users,
            "query": query,
            "group": group_id,
            "sender": sender_id,
            "message": "",
        })

    def post(self, request):
        group_id = request.data.get("group")
        user_id = request.data.get("user")
        sender_id = request.data.get("sender", None)

        group = get_object_or_404(Group, pk=group_id)
        receiver = get_object_or_404(User, pk=user_id)
        sender = get_object_or_404(User, pk=sender_id) if sender_id else group.created_by

        if GroupMember.objects.filter(group=group, user=receiver).exists():
            return Response({
                "message": "This user is already a member of the group.",
                "users": [],
                "query": "",
                "group": group_id,
                "sender": sender_id,
            })

        if GroupInvite.objects.filter(group=group, receiver=receiver, status="pending").exists():
            return Response({
                "message": "An invitation has already been sent to this user.",
                "users": [],
                "query": "",
                "group": group_id,
                "sender": sender_id,
            })

        invite = GroupInvite.objects.create(group=group, sender=sender, receiver=receiver)
        Notification.objects.create(
            user=receiver,
            message=f"{sender.username} invited you to join group '{group.name}'.",
            link=f"/groups/invite/{invite.id}/respond/",
        )

        return Response({
            "message": "Invitation sent and alert created.",
            "users": [],
            "query": "",
            "group": group_id,
            "sender": sender_id,
        })


class GroupInviteRespondHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "group_invite_response.html"

    def get(self, request, pk):
        invite = get_object_or_404(GroupInvite, pk=pk)
        return Response({"invite": invite, "message": ""})

    def post(self, request, pk):
        invite = get_object_or_404(GroupInvite, pk=pk)
        action = request.data.get("action")
        message = ""

        if invite.status != "pending":
            message = f"This invitation is already {invite.status}."
        elif action == "accept":
            if not GroupMember.objects.filter(group=invite.group, user=invite.receiver).exists():
                GroupMember.objects.create(group=invite.group, user=invite.receiver)
            invite.status = "accepted"
            invite.responded_at = timezone.now()
            invite.save()
            Notification.objects.create(
                user=invite.sender,
                message=f"{invite.receiver.username} accepted your invite to join '{invite.group.name}'.",
                link=f"/groups/{invite.group.id}/view/",
            )
            message = "You accepted the invite and have been added to the group."
        elif action == "decline":
            invite.status = "declined"
            invite.responded_at = timezone.now()
            invite.save()
            Notification.objects.create(
                user=invite.sender,
                message=f"{invite.receiver.username} declined the invite to join '{invite.group.name}'.",
            )
            message = "Invite declined."
        else:
            message = "No valid action was provided."

        return Response({"invite": invite, "message": message})


class AddGroupExpenseHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "add_group_expense.html"

    def get(self, request):
        return Response()

    def post(self, request):
        group_id = request.data.get("group")
        user_id = request.data.get("user")
        amount = request.data.get("amount")
        description = request.data.get("description")
        date = request.data.get("date")

        group = get_object_or_404(Group, pk=group_id)
        user = get_object_or_404(User, pk=user_id)

        GroupExpense.objects.create(
            group=group,
            user=user,
            amount=amount,
            description=description,
            date=date,
        )

        return Response({"message": "Group expense added successfully"})


class SearchUsersAPI(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        query = request.GET.get("q", "").strip()
        group_id = request.GET.get("group_id")

        if not query or not group_id:
            return Response({"users": [], "error": "Query and group_id required"}, status=400)

        group = get_object_or_404(Group, pk=group_id)

        # Search by username or ID
        users = User.objects.filter(
            username__icontains=query
        ) | User.objects.filter(
            id__iexact=query
        )

        # Exclude already members
        users = users.exclude(
            pk__in=GroupMember.objects.filter(group=group).values_list("user_id", flat=True)
        )

        # Exclude already invited (pending)
        users = users.exclude(
            pk__in=GroupInvite.objects.filter(group=group, status="pending").values_list("receiver_id", flat=True)
        )

        users = users.order_by("username")[:10]

        return Response({
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email if hasattr(u, 'email') else "",
                }
                for u in users
            ]
        })


class InviteUserAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        group_id = request.data.get("group_id")
        user_id = request.data.get("user_id")
        sender_id = request.user.id if request.user.is_authenticated else request.data.get("sender_id")

        if not all([group_id, user_id, sender_id]):
            return Response({"error": "Missing required fields"}, status=400)

        try:
            group = Group.objects.get(pk=group_id)
            receiver = User.objects.get(pk=user_id)
            sender = User.objects.get(pk=sender_id)
        except (Group.DoesNotExist, User.DoesNotExist):
            return Response({"error": "Invalid group or user"}, status=404)

        # Check if already a member
        if GroupMember.objects.filter(group=group, user=receiver).exists():
            return Response({
                "success": False,
                "message": "This user is already a member of the group."
            }, status=400)

        # Check if already invited
        if GroupInvite.objects.filter(group=group, receiver=receiver, status="pending").exists():
            return Response({
                "success": False,
                "message": "An invitation has already been sent to this user."
            }, status=400)

        # Create invite and notification
        invite = GroupInvite.objects.create(group=group, sender=sender, receiver=receiver)
        Notification.objects.create(
            user=receiver,
            message=f"{sender.username} invited you to join group '{group.name}'.",
            link=f"/groups/invite/{invite.id}/respond/",
        )

        return Response({
            "success": True,
            "message": f"Invitation sent to {receiver.username}",
            "invite": {
                "id": invite.id,
                "receiver": receiver.username,
                "status": invite.status,
            }
        })


class InviteRespondAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request, pk):
        invite = get_object_or_404(GroupInvite, pk=pk)
        action = request.data.get("action")

        if invite.status != "pending":
            return Response({
                "success": False,
                "message": f"This invitation is already {invite.status}."
            }, status=400)

        if action == "accept":
            if not GroupMember.objects.filter(group=invite.group, user=invite.receiver).exists():
                GroupMember.objects.create(group=invite.group, user=invite.receiver)
            invite.status = "accepted"
            invite.responded_at = timezone.now()
            invite.save()
            Notification.objects.create(
                user=invite.sender,
                message=f"{invite.receiver.username} accepted your invite to join '{invite.group.name}'.",
                link=f"/groups/{invite.group.id}/view/",
            )
            return Response({
                "success": True,
                "message": "You accepted the invite and have been added to the group."
            })

        elif action == "decline":
            invite.status = "declined"
            invite.responded_at = timezone.now()
            invite.save()
            Notification.objects.create(
                user=invite.sender,
                message=f"{invite.receiver.username} declined the invite to join '{invite.group.name}'.",
            )
            return Response({
                "success": True,
                "message": "Invite declined."
            })

        else:
            return Response({
                "success": False,
                "message": "Invalid action. Use 'accept' or 'decline'."
            }, status=400)
