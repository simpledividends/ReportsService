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

not_parsed = {
    "model": ErrorResponse,
    "description": "Error: Report not found",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="report_not_parsed",
                        error_message="Report is not parsed (yet)",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}

not_payed = {
    "model": ErrorResponse,
    "description": "Error: Report not payed",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="report_not_payed",
                        error_message="Report is not payed (yet)",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}

too_large = {
    "model": ErrorResponse,
    "description": "Error: Report file is too large",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="file_too_large",
                        error_message="File is too large",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}


no_price = {
    "model": ErrorResponse,
    "description": "Error: Report does not have price",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="no_price",
                        error_message="Price not set for this report (yet)",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}


not_parsed_or_payed_or_no_price_or_zero_price = {
    "model": ErrorResponse,
    "description": "Error: Report not found or payed",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="report_not_parsed",
                        error_message="Report is not parsed (yet)",
                        error_loc=None,
                    ),
                    Error(
                        error_key="report_already_payed",
                        error_message="Report is already payed",
                        error_loc=None,
                    ),
                    Error(
                        error_key="no_price",
                        error_message="Price not set for this report (yet)",
                        error_loc=None,
                    ),
                    Error(
                        error_key="zero_price",
                        error_message="Report is free",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}


too_many_reports = {
    "model": ErrorResponse,
    "description": "Error: User has too many reports",
    "content": {
        "application/json": {
            "example": ErrorResponse(
                errors=[
                    Error(
                        error_key="too_many_reports",
                        error_message="User has too many reports",
                        error_loc=None,
                    ),
                ],
            ),
        },
    },
}
