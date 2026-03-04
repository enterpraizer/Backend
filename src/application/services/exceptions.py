class UserAlreadyExistsError(Exception):
    pass


class UserNotFound(Exception):
    pass


class UserPermissionDenied(Exception):
    pass


class UserValidationError(Exception):
    pass
