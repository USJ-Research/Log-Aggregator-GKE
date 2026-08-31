import logging
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseServerError, HttpResponseForbidden
from . models import Topic, Room, Message
from . forms import (
    RoomForm, UserRegistrationForm, MessageForm, UserUpdateForm,
    ProfileUpdateForm, SafePasswordResetForm
    )
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.models import User, auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views

from django.db import connections
from django.db.utils import OperationalError
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    """
    Custom CSRF failure handler, wired up via CSRF_FAILURE_VIEW in settings.py.
    Django calls this instead of returning its default 403 page whenever
    CsrfViewMiddleware rejects a request. Setting request.log_tag here lets
    RequestLoggingMiddleware pick it up and emit it in the standard
    TAG "METHOD path" status log format, same as every other view.
    """
    request.log_tag = "CSRF_FAILURE"
    return HttpResponseForbidden("<h1>Forbidden 403!</h1>")


def home(request):
    try:
        q = request.GET.get('q') if request.GET.get('q') else ''

        rooms = Room.objects.distinct().filter(
            Q(topic__name__icontains=q) |
            Q(name__icontains=q)
        )
        rooms_count = rooms.count()
        topics = Topic.objects.all()[:5]
        activities = Message.objects.all()

        request.log_tag = "HOME_SEARCH" if q else "HOME_ACCESSED"

        context = {'rooms': rooms, 'topics': topics, 'rooms_count': rooms_count, 'activities': activities}
        return render(request, 'home/index.html', context)
    except OperationalError:
        request.log_tag = "HOME_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"HOME_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


def login(request):
    if request.user.is_authenticated:
        messages.info(request, "You Have Already Loged-In!")
        request.log_tag = "LOGIN_FINISHED"
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            auth_user = auth.authenticate(username=username, password=password)
        except OperationalError:
            request.log_tag = "LOGIN_FAILED: database unavailable"
            return HttpResponse("Service Unavailable", status=503)
        except Exception as e:
            request.log_tag = f"LOGIN_FAILED: {str(e)}"
            return HttpResponseServerError("Internal Server Error")

        if auth_user is not None:
            auth.login(request, auth_user)
            messages.success(request, "Successfully Loged-In!")
            request.log_tag = "LOGIN_SUCCESS"
            return redirect('home')
        else:
            messages.error(request, "User Doesn't Exist!")
            request.log_tag = "INVALID_REQUEST"
            return render(request, 'home/login.html', status=401)

    request.log_tag = "LOGIN_ACCESSED"
    return render(request, 'home/login.html')


def logout(request):
    if not (request.user.is_authenticated):
        messages.info(request, "You Have Not Loged-In!")
        request.log_tag = "LOGOUT_FINISHED"
        return redirect('home')

    username = request.user.username
    try:
        auth.logout(request)
    except OperationalError:
        request.log_tag = "LOGOUT_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"LOGOUT_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")

    messages.success(request, "Successfully Loged Out!")
    request.log_tag = "LOGOUT_SUCCESS"
    return redirect('home')


def register(request):
    form = UserRegistrationForm()
    status_code = 200

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)

        if form.is_valid():
            try:
                new_user = form.save(commit=False)
                new_user.username = new_user.username.lower()
                new_user.save()
            except OperationalError:
                request.log_tag = "REGISTER_FAILED: database unavailable"
                return HttpResponse("Service Unavailable", status=503)
            except Exception as e:
                request.log_tag = f"REGISTER_FAILED: {str(e)}"
                return HttpResponseServerError("Internal Server Error")

            messages.success(request, "Account Created Successfully!")
            auth.login(request, new_user)
            request.log_tag = "REGISTER_SUCCESS"
            return redirect('home')
        else:
            request.log_tag = "INVALID_REQUEST"
            status_code = 400

    if not hasattr(request, 'log_tag'):
        request.log_tag = "REGISTER_ACCESSED"
    context = {'form': form}
    return render(request, 'home/register.html', context, status=status_code)


@login_required
def room(request, pk):
    try:
        room = Room.objects.get(id=pk)
        room_messages = room.message_set.all().order_by('-created')
        members = room.participants.all()

        if request.method == 'POST':
            new_msg = request.POST.get('body')

            if new_msg != '':
                Message.objects.create(
                    user=request.user,
                    room=room,
                    body=new_msg
                )
                room.participants.add(request.user)
                request.log_tag = "ROOM_SUCCESS"
                return redirect('room', pk=room.id)
            else:
                request.log_tag = "INVALID_REQUEST"
                context = {'room': room, 'room_messages': room_messages, 'members': members}
                return render(request, 'home/room.html', context, status=400)

        request.log_tag = "ROOM_ACCESSED"
        context = {'room': room, 'room_messages': room_messages, 'members': members}
        return render(request, 'home/room.html', context)
    except OperationalError:
        request.log_tag = "ROOM_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"ROOM_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


@login_required
def createRoom(request):
    topics = Topic.objects.all()
    form = RoomForm()
    status_code = 200

    if request.method == 'POST':
        form = RoomForm(request.POST)

        if form.is_valid():
            try:
                new_room = form.save(commit=False)
                new_room.host = request.user

                topic_name = request.POST.get('topic')
                topic, created = Topic.objects.get_or_create(name=topic_name)
                new_room.topic = topic
                new_room.save()
            except OperationalError:
                request.log_tag = "CREATEROOM_FAILED: database unavailable"
                return HttpResponse("Service Unavailable", status=503)
            except Exception as e:
                request.log_tag = f"CREATEROOM_FAILED: {str(e)}"
                return HttpResponseServerError("Internal Server Error")

            messages.success(request, "Room Created Successfully!")
            request.log_tag = "CREATEROOM_SUCCESS"
            return redirect('room', pk=new_room.pk)
        else:
            request.log_tag = "INVALID_REQUEST"
            status_code = 400

    if not hasattr(request, 'log_tag'):
        request.log_tag = "CREATEROOM_ACCESSED"
    context = {'form': form, 'topics': topics}
    return render(request, 'home/room_create.html', context, status=status_code)


@login_required
def updateRoom(request, pk):
    status_code = 200
    try:
        topics = Topic.objects.all()
        room = Room.objects.get(id=pk)
        current_topic = room.topic

        if request.user != room.host:
            request.log_tag = "FORBIDDEN_ACCESS"
            return HttpResponse("<h1>Forbidden 403!</h1>", status=403)

        form = RoomForm(instance=room)
        if request.method == 'PUT':
            form = RoomForm(request.POST, instance=room)

            if form.is_valid():
                alt_room = form.save(commit=False)

                topic_name = request.POST.get('topic')
                topic, created = Topic.objects.get_or_create(name=topic_name)
                alt_room.topic = topic
                alt_room.save()

                count = current_topic.room_set.all().count()
                if count == 0:
                    current_topic.delete()

                messages.success(request, "Room Updated Successfully!")
                request.log_tag = "UPDATEROOM_SUCCESS"
                return redirect('room', pk=room.pk)
            else:
                request.log_tag = "INVALID_REQUEST"
                status_code = 400

        if not hasattr(request, 'log_tag'):
            request.log_tag = "UPDATEROOM_ACCESSED"
        context = {'form': form, 'room': room, 'topics': topics}
        return render(request, 'home/room_update.html', context, status=status_code)
    except OperationalError:
        request.log_tag = "UPDATEROOM_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"UPDATEROOM_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


@login_required
def deleteRoom(request, pk):
    try:
        room = Room.objects.get(id=pk)
        current_topic = room.topic

        if request.user != room.host:
            request.log_tag = "FORBIDDEN_ACCESS"
            return HttpResponse("<h1>Forbidden 403!</h1>", status=403)

        if request.method == 'DELETE':
            room.delete()

            count = current_topic.room_set.all().count()
            if count == 0:
                current_topic.delete()

            messages.success(request, "Room Deleted Successfully!")
            request.log_tag = "DELETEROOM_SUCCESS"
            return redirect('home')

        request.log_tag = "DELETEROOM_ACCESSED"
        context = {'room': room}
        return render(request, 'home/room_delete.html', context)
    except OperationalError:
        request.log_tag = "DELETEROOM_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"DELETEROOM_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


@login_required
def deleteMessage(request, pk):
    try:
        msg = Message.objects.get(id=pk)
        room = msg.room
        current_user = request.user

        if request.user != msg.user:
            request.log_tag = "FORBIDDEN_ACCESS"
            return HttpResponse("<h1>Forbidden 403!</h1>", status=403)

        if request.method == 'DELETE':
            msg.delete()

            count = Message.objects.filter(room=room, user=current_user).count()
            if count == 0:
                room.participants.remove(current_user)

            messages.success(request, "Message Deleted Successfully!")
            request.log_tag = "DELETEMESSAGE_SUCCESS"
            return redirect('room', pk=room.pk)

        request.log_tag = "DELETEMESSAGE_ACCESSED"
        context = {'msg': msg, 'room': room}
        return render(request, 'home/message_delete.html', context)
    except OperationalError:
        request.log_tag = "DELETEMESSAGE_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"DELETEMESSAGE_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


def profile(request, username):
    try:
        current_user = User.objects.get(username=username)
        rooms = current_user.room_set.all()
        activities = Message.objects.all()
        topics = Topic.objects.all()

        request.log_tag = "PROFILE_ACCESSED"
        context = {'current_user': current_user, 'rooms': rooms, 'activities': activities, 'topics': topics}
        return render(request, 'home/profile.html', context)
    except OperationalError:
        request.log_tag = "PROFILE_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"PROFILE_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


@login_required
def profileUpdate(request, username):
    status_code = 200
    try:
        current_user = User.objects.get(username=username)
        if current_user != request.user:
            request.log_tag = "FORBIDDEN_ACCESS"
            return HttpResponse("<h1>Forbidden 403!</h1>", status=403)

        form = UserUpdateForm(instance=current_user)
        p_form = ProfileUpdateForm(instance=current_user.profile)

        if request.method == 'PUT':
            form = UserUpdateForm(request.POST, instance=current_user)
            p_form = ProfileUpdateForm(request.POST, request.FILES, instance=current_user.profile)

            if form.is_valid():
                try:
                    alt_user = form.save(commit=False)
                    alt_user.username = alt_user.username.lower()
                    alt_user.save()
                    p_form.save()
                except ClientError:
                    request.log_tag = "PROFILEUPDATE_FAILED: storage unavailable"
                    return HttpResponse("Bad Gateway", status=502)
                except OperationalError:
                    request.log_tag = "PROFILEUPDATE_FAILED: database unavailable"
                    return HttpResponse("Service Unavailable", status=503)

                messages.success(request, "Profile Updated Successfully!")
                request.log_tag = "PROFILEUPDATE_SUCCESS"
                return redirect('profile', username=alt_user.username)
            else:
                request.log_tag = "INVALID_REQUEST"
                status_code = 400

        if not hasattr(request, 'log_tag'):
            request.log_tag = "PROFILEUPDATE_ACCESSED"
        context = {'current_user': current_user, 'form': form, 'p_form': p_form}
        return render(request, 'home/profile_update.html', context, status=status_code)
    except OperationalError:
        request.log_tag = "PROFILEUPDATE_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"PROFILEUPDATE_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


@login_required
def profileDelete(request, username):
    try:
        current_user = User.objects.get(username=username)
        if request.user != current_user:
            request.log_tag = "FORBIDDEN_ACCESS"
            return HttpResponse("<h1>Forbidden 403!</h1>", status=403)

        if request.method == 'DELETE':
            current_user.delete()
            messages.success(request, "Account Deleted Successfully!")
            request.log_tag = "PROFILEDELETE_SUCCESS"
            return redirect('home')

        request.log_tag = "PROFILEDELETE_ACCESSED"
        context = {'current_user': current_user}
        return render(request, 'home/profile_delete.html', context)
    except OperationalError:
        request.log_tag = "PROFILEDELETE_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"PROFILEDELETE_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


def topicView(request):
    try:
        q = request.GET.get('q') if request.GET.get('q') else ''
        topics = Topic.objects.filter(
            Q(name__icontains=q)
        )[:5]

        request.log_tag = "TOPICVIEW_SEARCH" if q else "TOPICVIEW_ACCESSED"

        context = {'topics': topics}
        return render(request, 'home/topics.html', context)
    except OperationalError:
        request.log_tag = "TOPICVIEW_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"TOPICVIEW_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


def activityView(request):
    try:
        activities = Message.objects.all()
        request.log_tag = "ACTIVITYVIEW_ACCESSED"
        context = {'activities': activities}
        return render(request, 'home/activity.html', context)
    except OperationalError:
        request.log_tag = "ACTIVITYVIEW_FAILED: database unavailable"
        return HttpResponse("Service Unavailable", status=503)
    except Exception as e:
        request.log_tag = f"ACTIVITYVIEW_FAILED: {str(e)}"
        return HttpResponseServerError("Internal Server Error")


def health(request):
    for db_name in connections:
        try:
            connections[db_name].cursor()
        except OperationalError:
            request.log_tag = "HEALTH_FAILED"
            return HttpResponse("Status: DB Down", status=503)
    request.log_tag = "HEALTH_SUCCESS"
    return HttpResponse("Health OK", status=200)


def start(request):
    try:
        request.log_tag = "START_SUCCESS"
        return HttpResponse("Started", status=200)
    except Exception:
        request.log_tag = "START_FAILED"
        return HttpResponse("Start Failed", status=503)


def ready(request):
    for db_name in connections:
        try:
            connections[db_name].cursor()
        except OperationalError:
            request.log_tag = "READY_FAILED"
            return HttpResponse("Status: DB Down", status=503)
    request.log_tag = "READY_SUCCESS"
    return HttpResponse("Ready", status=200)


def live(request):
    for db_name in connections:
        try:
            connections[db_name].cursor()
        except OperationalError:
            request.log_tag = "LIVE_FAILED"
            return HttpResponse("Status: DB Down", status=503)
    request.log_tag = "LIVE_SUCCESS"
    return HttpResponse("Live", status=200)


class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'home/reset_password.html'
    form_class = SafePasswordResetForm

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except OperationalError:
            self.request.log_tag = "PASSWORDRESET_FAILED: database unavailable"
            return HttpResponse("Service Unavailable", status=503)
        except RuntimeError:
            self.request.log_tag = "PASSWORDRESET_EMAIL_FAILED"
            return HttpResponseServerError("<h1>Internal Server Error 500!</h1>")
        except Exception as e:
            self.request.log_tag = f"PASSWORDRESET_FAILED: {str(e)}"
            return HttpResponseServerError("Internal Server Error")
        self.request.log_tag = "PASSWORDRESET_ACCESSED"
        return response

    def form_invalid(self, form):
        self.request.log_tag = "INVALID_REQUEST"
        response = super().form_invalid(form)
        response.status_code = 400
        return response


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'home/reset_password_confirm.html'

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except OperationalError:
            self.request.log_tag = "PASSWORDRESETCONFIRM_FAILED: database unavailable"
            return HttpResponse("Service Unavailable", status=503)
        except Exception as e:
            self.request.log_tag = f"PASSWORDRESETCONFIRM_FAILED: {str(e)}"
            return HttpResponseServerError("Internal Server Error")
        self.request.log_tag = "PASSWORDRESETCONFIRM_ACCESSED"
        return response

    def form_invalid(self, form):
        self.request.log_tag = "INVALID_REQUEST"
        response = super().form_invalid(form)
        response.status_code = 400
        return response