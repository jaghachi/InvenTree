# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _

from django.contrib import admin, messages
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe

from users.models import RuleSet

User = get_user_model()


class RuleSetInline(admin.TabularInline):
    """
    Class for displaying inline RuleSet data in the Group admin page.
    """

    model = RuleSet
    can_delete = False
    verbose_name = 'Ruleset'
    verbose_plural_name = 'Rulesets'
    fields = ['name'] + [option for option in RuleSet.RULE_OPTIONS]
    readonly_fields = ['name']
    max_num = len(RuleSet.RULESET_CHOICES)
    min_num = 1
    extra = 0


class InvenTreeGroupAdminForm(forms.ModelForm):
    """
    Custom admin form for the Group model.

    Adds the ability for editing user membership directly in the group admin page.
    """

    class Meta:
        model = Group
        exclude = []
        fields = [
            'name',
            'users',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            # Populate the users field with the current Group users.
            self.fields['users'].initial = self.instance.user_set.all()

    # Add the users field.
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('users', False),
        label=_('Users'),
        help_text=_('Select which users are assigned to this group')
    )

    def save_m2m(self):
        # Add the users to the Group.

        self.instance.user_set.set(self.cleaned_data['users'])

    def save(self, *args, **kwargs):
        # Default save
        instance = super().save()
        # Save many-to-many data
        self.save_m2m()
        return instance


class RoleGroupAdmin(admin.ModelAdmin):
    """
    Custom admin interface for the Group model
    """

    form = InvenTreeGroupAdminForm

    inlines = [
        RuleSetInline,
    ]

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # Hide RuleSetInline in the 'Add role' view
            if not isinstance(inline, RuleSetInline) or obj is not None:
                yield inline.get_formset(request, obj), inline

    filter_horizontal = ['permissions']

    def save_model(self, request, obj, form, change):
        """
            This method serves two purposes:
            - show warning message whenever the group users belong to multiple groups
            - skip saving of the group instance model as inlines needs to be saved before.
        """

        # Get form cleaned data
        users = form.cleaned_data['users']

        # Check for users who are members of multiple groups
        warning_message = ''
        for user in users:
            if user.groups.all().count() > 1:
                warning_message += f'<br>- <b>{user.username}</b> is member of: '
                for idx, group in enumerate(user.groups.all()):
                    warning_message += f'<b>{group.name}</b>'
                    if idx < len(user.groups.all()) - 1:
                        warning_message += ', '

        # If any, display warning message when group is saved
        if warning_message:
            warning_message = mark_safe(_(f'The following users are members of multiple groups:'
                                          f'{warning_message}'))
            messages.add_message(request, messages.WARNING, warning_message)

    def save_formset(self, request, form, formset, change):
        # Save inline Rulesets
        formset.save()
        # Save Group instance and update permissions
        form.instance.save(update_fields=['name'])


class InvenTreeUserAdmin(UserAdmin):
    """
    Custom admin page for the User model.

    Hides the "permissions" view as this is now handled
    entirely by groups and RuleSets.

    (And it's confusing!)
    """

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )


admin.site.unregister(Group)
admin.site.register(Group, RoleGroupAdmin)

admin.site.unregister(User)
admin.site.register(User, InvenTreeUserAdmin)
