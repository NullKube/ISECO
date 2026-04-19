from django.shortcuts import get_object_or_404, redirect
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework.response import Response
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from .models import Goal
from .serializers import GoalSerializer
from .feasibility_engine import (
    check_goal_feasibility,
    find_next_feasible_date,
    get_all_active_goals_sorted,
    reschedule_all_goals,
    get_goal_with_shift_suggestion,
    calculate_monthly_savings
)
from users.models import User


# ========== CHECK GOAL FEASIBILITY (BEFORE CREATION) ==========
class CheckGoalFeasibilityAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        """
        Check if a proposed goal is feasible before creating it.
        Returns feasibility status and suggested deadline if not feasible.
        """
        if 'user_id' not in request.session:
            return Response({"success": False, "error": "Authentication required"}, status=401)

        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)

        # Get proposed goal data
        name = request.data.get("name", "Unnamed Goal")
        target_amount = request.data.get("target_amount")
        priority = request.data.get("priority", 5)
        deadline_str = request.data.get("deadline")

        if not target_amount or not deadline_str:
            return Response({
                "success": False,
                "error": "Target amount and deadline are required"
            }, status=400)

        try:
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response({
                "success": False,
                "error": "Invalid deadline format. Use YYYY-MM-DD"
            }, status=400)

        # Create a temporary goal object (not saved) for feasibility check
        temp_goal = Goal(
            user=user,
            name=name,
            target_amount=float(target_amount),
            priority=int(priority),
            deadline=deadline,
            amount_saved=0,
            status='active'
        )

        # Check feasibility
        feasibility = check_goal_feasibility(temp_goal, user=user)

        result = {
            "success": True,
            "is_feasible": feasibility['is_feasible'],
            "feasibility_data": feasibility,
            "suggestion": None
        }

        if not feasibility['is_feasible']:
            # Find next feasible date
            next_feasible = find_next_feasible_date(temp_goal, user=user)
            result['suggestion'] = {
                'new_deadline': next_feasible['feasible_date'].strftime('%Y-%m-%d') if next_feasible['feasible_date'] else None,
                'months_delay': next_feasible['months_delay'],
                'reason': next_feasible['reason']
            }

        return Response(result)


# ========== ADD GOAL ==========
class GoalAddHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "add_goal.html"

    def get(self, request):
        if 'user_id' not in request.session:
            return redirect('/users/login/')
        return Response()

    def post(self, request):
        """
        Create a goal after feasibility check.
        If goal was checked and approved, use the approved deadline.
        """
        if 'user_id' not in request.session:
            return redirect('/users/login/')

        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)

        name = request.data.get("name")
        target_amount = request.data.get("target_amount")
        priority = request.data.get("priority")
        deadline = request.data.get("deadline")
        amount_saved = 0

        # Validate name
        if not name:
            name = f"Goal {Goal.objects.filter(user=user).count() + 1}"

        goal = Goal.objects.create(
            user=user,
            name=name,
            target_amount=target_amount,
            priority=priority,
            deadline=deadline,
            amount_saved=amount_saved,
            status="active"
        )

        return Response({
            "message": "Goal created successfully",
            "goal_id": goal.id,
            "goal_name": goal.name,
            "deadline": deadline,
            "redirect_url": "/goals/list/"
        })


# ========== LIST GOALS ==========
class GoalListHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "goal_list.html"

    def get(self, request):
        if 'user_id' not in request.session:
            return redirect('/users/login/')

        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)

        # Fetch active and completed goals
        active_goals = get_all_active_goals_sorted(user)
        completed_goals = Goal.objects.filter(status="completed", user=user).order_by('-created_at')

        # Calculate analysis for each active goal
        active_with_analysis = []
        for goal in active_goals:
            try:
                feasibility = check_goal_feasibility(goal, user=user)
                shift_suggestion = None
                
                if not feasibility['is_feasible']:
                    next_feasible = find_next_feasible_date(goal, user=user)
                    if next_feasible['feasible_date']:
                        shift_suggestion = {
                            'new_deadline': next_feasible['feasible_date'],
                            'reason': next_feasible['reason']
                        }
                
                today = datetime.now().date()
                remaining_days = (goal.deadline - today).days
                
                active_with_analysis.append({
                    'goal': goal,
                    'analysis': {
                        'is_feasible': feasibility['is_feasible'],
                        'current_balance': goal.amount_saved,
                        'projected_balance_at_deadline': goal.amount_saved + (feasibility['actual_monthly'] * (remaining_days / 30)),
                        'required_monthly_savings': feasibility['required_monthly'],
                        'actual_monthly_savings': feasibility['actual_monthly'],
                        'shift_suggestion': shift_suggestion,
                        'feasibility_reason': feasibility['reason']
                    }
                })
            except Exception as e:
                # Fallback if analysis fails
                active_with_analysis.append({
                    'goal': goal,
                    'analysis': {
                        'is_feasible': False,
                        'current_balance': goal.amount_saved,
                        'projected_balance_at_deadline': 0,
                        'required_monthly_savings': 0,
                        'actual_monthly_savings': 0,
                        'shift_suggestion': None,
                        'feasibility_reason': f'Error calculating analysis: {str(e)}'
                    }
                })

        return Response({
            "active_goals": active_with_analysis,
            "completed_goals": completed_goals,
            "current_user": user
        })


# ========== GOAL DETAIL ==========
class GoalDetailHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "goal_detail.html"

    def get(self, request, pk):
        if 'user_id' not in request.session:
            return redirect('/users/login/')
        
        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)
        
        goal = get_object_or_404(Goal, pk=pk, user=user)
        feasibility = check_goal_feasibility(goal, user=user)
        return Response({"goal": goal, "feasibility": feasibility})


# ========== EDIT GOAL ==========
class GoalEditHTML(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "edit_goal.html"

    def get(self, request, pk):
        if 'user_id' not in request.session:
            return redirect('/users/login/')
        
        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)
        
        goal = get_object_or_404(Goal, pk=pk, user=user)
        return Response({"goal": goal})

    def post(self, request, pk):
        if 'user_id' not in request.session:
            return redirect('/users/login/')
        
        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)
        
        goal = get_object_or_404(Goal, pk=pk, user=user)

        # Update editable fields
        if "target_amount" in request.data:
            goal.target_amount = request.data.get("target_amount")
        if "priority" in request.data:
            goal.priority = request.data.get("priority")
        if "deadline" in request.data:
            goal.deadline = request.data.get("deadline")

        goal.save()

        # Get updated feasibility info
        feasibility = check_goal_feasibility(goal, user=user)

        return Response({
            "goal": goal,
            "feasibility": feasibility,
            "message": "Goal updated successfully!"
        }, template_name="goal_detail.html")


# ========== CONFIRM DEADLINE SHIFT ==========
class ConfirmShiftAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request, pk):
        if 'user_id' not in request.session:
            return Response({"success": False, "error": "Authentication required"}, status=401)

        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)
        goal = get_object_or_404(Goal, pk=pk, user=user)

        # Update deadline to the suggested date
        new_deadline = request.data.get("new_deadline")
        if new_deadline:
            if isinstance(new_deadline, str):
                try:
                    goal.deadline = datetime.strptime(new_deadline, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    return Response({
                        "success": False,
                        "error": "Invalid deadline format"
                    }, status=400)
            else:
                goal.deadline = new_deadline
            
            # Save original deadline if not already saved
            if not goal.original_deadline:
                goal.original_deadline = goal.deadline
            
            goal.save()

        # Apply cascade adjustments - re-evaluate all goals
        adjustments = reschedule_all_goals(user)

        return Response({
            "success": True,
            "primary_goal": {
                "goal_id": goal.id,
                "goal_name": goal.name,
                "new_deadline": goal.deadline.strftime('%Y-%m-%d'),
                "priority": goal.priority
            },
            "cascade_adjustments": adjustments,
            "message": f"Goal deadline updated! {len(adjustments)} other goals adjusted for optimal feasibility."
        }, status=200)


# ========== OPTIMIZE ALL GOALS BY PRIORITY ==========
class OptimizeGoalsByPriorityAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request):
        if 'user_id' not in request.session:
            return Response({"success": False, "error": "Authentication required"}, status=401)

        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)

        try:
            # Re-evaluate and reschedule all goals by priority
            adjustments = reschedule_all_goals(user)

            return Response({
                "success": True,
                "results": adjustments,
                "message": f"Successfully optimized {len(adjustments)} goal(s) by priority"
            }, status=200)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                "success": False,
                "error": str(e)
            }, status=500)


# ========== MARK GOAL AS ACHIEVED ==========
class MarkAchievedAPI(APIView):
    renderer_classes = [JSONRenderer]

    def post(self, request, pk):
        if 'user_id' not in request.session:
            return Response({"success": False, "error": "Authentication required"}, status=401)

        user_id = request.session['user_id']
        user = get_object_or_404(User, pk=user_id)
        goal = get_object_or_404(Goal, pk=pk, user=user)

        # Mark goal as completed
        goal.status = "completed"
        goal.save()

        return Response({
            "goal_id": goal.id,
            "goal_name": goal.name,
            "message": "Goal marked as completed!",
            "success": True
        }, status=200)
