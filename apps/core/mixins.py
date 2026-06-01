from django.core.exceptions import PermissionDenied


from django.core.exceptions import PermissionDenied


class MerchantRequiredMixin:
    def get_merchant(self):
        user = self.request.user

        staff_profile = getattr(user, "staff_profile", None)
        merchant = getattr(staff_profile, "merchant", None)

        if merchant:
            return merchant

        if user.is_superuser:
            return None

        raise PermissionDenied("لا يوجد محل مرتبط بهذا المستخدم.")

        

    def get_staff_profile(self):
        user = self.request.user

        staff_profile = getattr(user, "staff_profile", None)

        if staff_profile:
            return staff_profile

        if user.is_superuser:
            return None

        raise PermissionDenied("لا يوجد ملف موظف مرتبط بهذا المستخدم.")

        

    def get_role(self):
        staff_profile = self.get_staff_profile()

        if staff_profile:
            return staff_profile.role

        if self.request.user.is_superuser:
            return "owner"

        return None


class OwnerRequiredMixin(MerchantRequiredMixin):
    allowed_roles = ["owner"]

    def dispatch(self, request, *args, **kwargs):
        if self.get_role() not in self.allowed_roles:
            raise PermissionDenied("ليس لديك صلاحية للوصول إلى هذه الصفحة.")
        return super().dispatch(request, *args, **kwargs)


class ManagerOrOwnerRequiredMixin(MerchantRequiredMixin):
    allowed_roles = ["owner", "manager"]

    def dispatch(self, request, *args, **kwargs):
        if self.get_role() not in self.allowed_roles:
            raise PermissionDenied("ليس لديك صلاحية للوصول إلى هذه الصفحة.")
        return super().dispatch(request, *args, **kwargs)


class CashierOrAboveRequiredMixin(MerchantRequiredMixin):
    allowed_roles = ["owner", "manager", "cashier"]

    def dispatch(self, request, *args, **kwargs):
        if self.get_role() not in self.allowed_roles:
            raise PermissionDenied("ليس لديك صلاحية للوصول إلى هذه الصفحة.")
        return super().dispatch(request, *args, **kwargs)