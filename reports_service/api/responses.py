from reports_service.models.common import Error, ErrorResponse

unprocessable_entity = {
    "model": ErrorResponse,
    "description": "Error: Unprocessable Entity",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="error_type.attr.desc",
                        error_message="error message",
                        error_loc=["body", "some_place"],
                    ),
                ],
            ),
        },
    },
}


forbidden = {
    "model": ErrorResponse,
    "description": "Error: Forbidden",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="forbidden",
                        error_message="Forbidden",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}

not_found = {
    "model": ErrorResponse,
    "description": "Error: Not found",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="not_found",
                        error_message="Resource not found",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}