from django import forms
from . models import Topic, Room, Message, Profile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from django import forms
from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.template import loader
from django.core.mail import EmailMultiAlternatives
from smtplib import SMTPException


class RoomForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(RoomForm, self).__init__(*args, **kwargs)

        self.fields['description'].widget.attrs.update({'placeholder':'First 300 Characters Will Display...'})

    class Meta:
        model = Room
        fields = ['name', 'description']



class UserRegistrationForm(UserCreationForm):

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email = email).exists():
            raise ValidationError("This Email Is Already Taken!")
        return email



class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']



class UserUpdateForm(forms.ModelForm):

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_username(self):
        current_user = self.instance
        username = self.cleaned_data.get('username').lower()

        if User.objects.filter(username = username).exclude(pk = current_user.pk).exists():
            raise ValidationError("This Username Is Already Taken!")
        return username      


    def clean_email(self):
        email = self.cleaned_data.get('email')
        current_user = self.instance

        if User.objects.filter(email = email).exclude(pk = current_user.pk).exists():
            raise ValidationError("This Email Is Already Taken!")
        return email



class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']



class SafePasswordResetForm(PasswordResetForm):
    """
    Reimplements PasswordResetForm.send_mail() without calling super().
    Django's own send_mail() catches SMTPException internally and only
    logs it (forms.py line ~437), never re-raising it - so overriding
    with a try/except around super().send_mail() never actually catches
    anything. This version builds and sends the email itself, so an
    SMTP failure propagates as RuntimeError up to the view.
    """
    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        try:
            email_message.send()
        except SMTPException as e:
            raise RuntimeError(str(e)) from e