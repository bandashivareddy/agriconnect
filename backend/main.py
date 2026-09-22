from contextvars import ContextVar
from datetime import datetime, timedelta, timezone, date
import logging
import re
import os
from pathlib import Path
import time
from typing import Literal
from uuid import UUID, uuid4

import jwt
from dotenv import load_dotenv
from decimal import Decimal
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.trustedhost import TrustedHostMiddleware
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field, ValidationError
from pwdlib import PasswordHash
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")


def configure_application_logging() -> logging.Logger:
    configured_level = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, configured_level, logging.INFO)
    if not isinstance(level, int):
        level = logging.INFO

    application_logger = logging.getLogger("agriconnect")
    application_logger.setLevel(level)

    if not application_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )
        application_logger.addHandler(handler)

    application_logger.propagate = False
    return application_logger


logger = configure_application_logging()
request_id_context: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)
REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128
DATABASE_CONNECT_TIMEOUT_SECONDS = 5
DATABASE_POOL_RECYCLE_SECONDS = 1800
MAX_DOCUMENT_UPLOAD_MB_DEFAULT = 5
STORED_DOCUMENT_REFERENCE_PREFIX = "provider-document:"
ALLOWED_DOCUMENT_FILE_TYPES = {
    ".pdf": ("application/pdf", b"%PDF-"),
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}


def get_positive_integer_setting(value: str | None, default: int) -> int:
    try:
        parsed_value = int(value) if value is not None else default
    except ValueError:
        return default
    return parsed_value if parsed_value > 0 else default


MAX_DOCUMENT_UPLOAD_MB = get_positive_integer_setting(
    os.getenv("MAX_DOCUMENT_UPLOAD_MB"), MAX_DOCUMENT_UPLOAD_MB_DEFAULT
)
MAX_DOCUMENT_UPLOAD_BYTES = MAX_DOCUMENT_UPLOAD_MB * 1024 * 1024
configured_document_storage = Path(
    os.getenv("DOCUMENT_STORAGE_DIR", "storage/provider_documents")
).expanduser()
DOCUMENT_STORAGE_DIR = (
    configured_document_storage
    if configured_document_storage.is_absolute()
    else BACKEND_DIR / configured_document_storage
).resolve()
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
DEFAULT_TRUSTED_HOSTS = (
    "localhost",
    "127.0.0.1",
    "testserver",
)


def parse_comma_separated_values(
    value: str | None,
    default: tuple[str, ...],
) -> list[str]:
    if value is None:
        return list(default)

    parsed_values = []
    for item in value.split(","):
        cleaned_item = item.strip()
        if cleaned_item and cleaned_item not in parsed_values:
            parsed_values.append(cleaned_item)
    return parsed_values


def api_docs_enabled(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


CORS_ORIGINS = parse_comma_separated_values(
    os.getenv("CORS_ORIGINS"), DEFAULT_CORS_ORIGINS
)
TRUSTED_HOSTS = parse_comma_separated_values(
    os.getenv("TRUSTED_HOSTS"), DEFAULT_TRUSTED_HOSTS
)
ENABLE_API_DOCS = api_docs_enabled(os.getenv("ENABLE_API_DOCS"))

REQUIRED_ENVIRONMENT_VARIABLES = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "JWT_SECRET",
)
missing_environment_variables = [
    name
    for name in REQUIRED_ENVIRONMENT_VARIABLES
    if not (value := os.getenv(name)) or not value.strip()
]
if missing_environment_variables:
    raise RuntimeError(
        "Missing required environment variable(s): "
        + ", ".join(missing_environment_variables)
    )

app = FastAPI(
    title="Agri Services Marketplace API",
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)


def get_request_id(incoming_request_id: str | None) -> str:
    candidate = (incoming_request_id or "").strip()
    if (
        candidate
        and len(candidate) <= MAX_REQUEST_ID_LENGTH
        and all(character.isalnum() or character in "-_." for character in candidate)
    ):
        return candidate
    return str(uuid4())


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    request_id = get_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    context_token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    response = None

    logger.info(
        "Request started request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )
    finally:
        if response is not None:
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            duration_ms = round((time.perf_counter() - started_at) * 1000)
            logger.info(
                "Request completed request_id=%s method=%s path=%s "
                "status_code=%s duration_ms=%s",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        request_id_context.reset(context_token)

    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=TRUSTED_HOSTS,
)

database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    database=os.environ["DB_NAME"],
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=DATABASE_POOL_RECYCLE_SECONDS,
    connect_args={"connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS},
)
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)

@app.get("/")
def home():
    return {"message": "Agri Services Marketplace API is running"}

@app.get("/health/database")
def database_health():
    with engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar()

    return {
        "status": "connected",
        "database": database_name
    }
@app.get("/services")
def list_services(
    category: str | None = None,
    supplier_id: int | None = None,
    category_id: int | None = None
):
    query = """
        SELECT
            ss.supplier_service_id,
            ss.service_name,
            ss.description,
            ss.pricing_unit,
            ss.base_price,
            ss.minimum_charge,
            ss.estimated_duration_minutes,
            sp.supplier_id,
            sp.business_name AS supplier_name,
            sp.average_rating,
            sc.category_id,
            sc.category_name
        FROM supplier_services ss
        JOIN supplier_profiles sp ON sp.supplier_id = ss.supplier_id
        JOIN service_categories sc ON sc.category_id = ss.category_id
        WHERE ss.is_active = TRUE
          AND sp.is_active = TRUE
          AND sp.verified_at IS NOT NULL
    """

    parameters = {}

    if category:
        query += " AND LOWER(sc.category_name) = LOWER(:category)"
        parameters["category"] = category

    if category_id is not None:
        query += " AND ss.category_id = :category_id AND sc.is_active = TRUE"
        parameters["category_id"] = category_id

    if supplier_id:
        query += " AND sp.supplier_id = :supplier_id"
        parameters["supplier_id"] = supplier_id

    query += " ORDER BY ss.created_at DESC"

    with engine.connect() as connection:
        services = connection.execute(
            text(query),
            parameters
        ).mappings().all()

    return [dict(service) for service in services]
@app.get("/equipment")
def list_equipment(
    category: str | None = None,
    supplier_id: int | None = None
):
    query = """
        SELECT
            e.equipment_id,
            e.equipment_name,
            e.brand,
            e.model,
            e.description,
            e.daily_rate,
            e.security_deposit,
            e.quantity_available,
            sp.supplier_id,
            sp.business_name AS supplier_name,
            sp.average_rating,
            ec.category_name
        FROM equipment e
        JOIN supplier_profiles sp ON sp.supplier_id = e.supplier_id
        LEFT JOIN equipment_categories ec
            ON ec.equipment_category_id = e.equipment_category_id
        WHERE e.is_active = TRUE
          AND sp.is_active = TRUE
          AND sp.verified_at IS NOT NULL
    """

    parameters = {}

    if category:
        query += " AND LOWER(ec.category_name) = LOWER(:category)"
        parameters["category"] = category

    if supplier_id:
        query += " AND sp.supplier_id = :supplier_id"
        parameters["supplier_id"] = supplier_id

    query += " ORDER BY e.created_at DESC"

    with engine.connect() as connection:
        equipment = connection.execute(
            text(query),
            parameters
        ).mappings().all()

    return [dict(item) for item in equipment]
class BookingCreate(BaseModel):
    farmer_id: int
    supplier_service_id: int
    farm_id: int | None = None
    service_address_id: int | None = None
    requested_start_at: datetime
    requested_end_at: datetime | None = None
    quantity: float = Field(gt=0)
    customer_notes: str | None = None


def _legacy_create_booking_unsafe(booking: BookingCreate):
    with engine.begin() as connection:
        farmer = connection.execute(
            text("""
                SELECT user_id
                FROM users
                WHERE user_id = :farmer_id
                  AND user_role = 'farmer'
            """),
            {"farmer_id": booking.farmer_id},
        ).mappings().first()

        if not farmer:
            raise HTTPException(status_code=404, detail="Farmer account not found.")

        service = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.supplier_id,
                    ss.service_name,
                    ss.pricing_unit,
                    ss.base_price
                FROM supplier_services ss
                JOIN supplier_profiles sp ON sp.supplier_id = ss.supplier_id
                WHERE ss.supplier_service_id = :service_id
                  AND ss.is_active = TRUE
                  AND sp.is_active = TRUE
            """),
            {"service_id": booking.supplier_service_id},
        ).mappings().first()

        if not service:
            raise HTTPException(
                status_code=404,
                detail="Available supplier service not found.",
            )

        if service["base_price"] is None:
            raise HTTPException(
                status_code=400,
                detail="This service requires a custom quote.",
            )

        if booking.farm_id:
            farm = connection.execute(
                text("""
                    SELECT farm_id
                    FROM farms
                    WHERE farm_id = :farm_id
                      AND farmer_id = :farmer_id
                """),
                {"farm_id": booking.farm_id, "farmer_id": booking.farmer_id},
            ).mappings().first()

            if not farm:
                raise HTTPException(
                    status_code=400,
                    detail="The selected farm does not belong to this farmer.",
                )

        if booking.service_address_id:
            address = connection.execute(
                text("""
                    SELECT address_id
                    FROM addresses
                    WHERE address_id = :address_id
                      AND user_id = :farmer_id
                """),
                {
                    "address_id": booking.service_address_id,
                    "farmer_id": booking.farmer_id,
                },
            ).mappings().first()

            if not address:
                raise HTTPException(
                    status_code=400,
                    detail="The selected address does not belong to this farmer.",
                )
            
        unit_price = Decimal(str(service["base_price"]))
        quantity = Decimal(str(booking.quantity))
        subtotal = unit_price * quantity
        booking_number = f"AGR-{datetime.now():%Y%m%d%H%M%S%f}"

        new_booking = connection.execute(
            text("""
                INSERT INTO bookings (
                    booking_number,
                    farmer_id,
                    supplier_id,
                    farm_id,
                    service_address_id,
                    requested_start_at,
                    requested_end_at,
                    status,
                    subtotal,
                    travel_fee,
                    platform_fee,
                    tax_amount,
                    discount_amount,
                    total_amount,
                    payment_status,
                    customer_notes
                )
                VALUES (
                    :booking_number,
                    :farmer_id,
                    :supplier_id,
                    :farm_id,
                    :service_address_id,
                    :requested_start_at,
                    :requested_end_at,
                    'pending',
                    :subtotal,
                    0,
                    0,
                    0,
                    0,
                    :total_amount,
                    'unpaid',
                    :customer_notes
                )
                RETURNING booking_id, booking_number, status, total_amount
            """),
            {
                "booking_number": booking_number,
                "farmer_id": booking.farmer_id,
                "supplier_id": service["supplier_id"],
                "farm_id": booking.farm_id,
                "service_address_id": booking.service_address_id,
                "requested_start_at": booking.requested_start_at,
                "requested_end_at": booking.requested_end_at,
                "subtotal": subtotal,
                "total_amount": subtotal,
                "customer_notes": booking.customer_notes,
            },
        ).mappings().one()

        connection.execute(
            text("""
                INSERT INTO booking_items (
                    booking_id,
                    supplier_service_id,
                    item_name,
                    quantity,
                    pricing_unit,
                    unit_price,
                    line_total,
                    scheduled_start_at,
                    scheduled_end_at
                )
                VALUES (
                    :booking_id,
                    :supplier_service_id,
                    :item_name,
                    :quantity,
                    :pricing_unit,
                    :unit_price,
                    :line_total,
                    :scheduled_start_at,
                    :scheduled_end_at
                )
            """),
            {
                "booking_id": new_booking["booking_id"],
                "supplier_service_id": service["supplier_service_id"],
                "item_name": service["service_name"],
                "quantity": quantity,
                "pricing_unit": service["pricing_unit"],
                "unit_price": unit_price,
                "line_total": subtotal,
                "scheduled_start_at": booking.requested_start_at,
                "scheduled_end_at": booking.requested_end_at,
            },
        )

        connection.execute(
            text("""
                INSERT INTO booking_status_history (
                    booking_id, old_status, new_status, changed_by, notes
                )
                VALUES (:booking_id, NULL, 'pending', :farmer_id, 'Booking created.')
            """),
            {
                "booking_id": new_booking["booking_id"],
                "farmer_id": booking.farmer_id,
            },
        )

    return {
        "message": "Booking created successfully.",
        **dict(new_booking),
    }



from officer_applications import SignupIntent, ApplicationFields, submit_application


class RegisterRequest(BaseModel):
    signup_intent: SignupIntent | None = None
    field_officer_application: ApplicationFields | None = None
    full_name: str = Field(min_length=2, max_length=100)
    email: str | None = Field(default=None, min_length=5, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    user_role: Literal["farmer", "supplier"] | None = None
    business_name: str | None = Field(default=None, max_length=150)

class ProviderProfileCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    business_registration_no: str | None = None
    gstin: str | None = None


class ProviderProfileUpdate(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    business_registration_no: str | None = None
    gstin: str | None = None


class ProviderVerificationDocumentCreate(BaseModel):
    document_type: str = Field(min_length=1, max_length=50)
    file_name: str = Field(min_length=1, max_length=255)
    file_url: str = Field(min_length=1, max_length=2048)


PROVIDER_DOCUMENT_TYPES = {
    "driving_licence": "Driving Licence",
    "voter_id": "Voter ID",
    "other_government_id": "Other Government ID",
    "vehicle_equipment_rc": "Vehicle / Equipment RC",
    "equipment_ownership_proof": "Equipment Ownership Proof",
    "service_trade_certificate": "Service / Trade Certificate",
    "gst_certificate": "GST Certificate",
    "business_registration": "Business Registration",
    "other_supporting_document": "Other Supporting Document",
}

PROVIDER_VERIFICATION_ELIGIBLE_DOCUMENT_TYPES = {
    "driving_licence",
    "voter_id",
    "other_government_id",
    "vehicle_equipment_rc",
    "service_trade_certificate",
}


def serialize_provider_document(document: dict) -> dict:
    document_data = dict(document)
    document_data["document_type_label"] = (
        PROVIDER_DOCUMENT_TYPES.get(
            document_data["document_type"],
            document_data["document_type"],
        )
    )
    document_data["has_uploaded_file"] = document_data["file_url"].startswith(
        STORED_DOCUMENT_REFERENCE_PREFIX
    )
    if document_data["has_uploaded_file"]:
        document_data["file_url"] = None
    return document_data


class LoginRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, min_length=5, max_length=150)
    password: str = Field(min_length=1, max_length=256)


def create_access_token(user_id: int, user_role: str):
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not configured.")

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    return jwt.encode(
        {
            "sub": str(user_id),
            "role": user_role,
            "exp": expires_at,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def get_effective_capabilities(
    connection,
    user_id: int,
    user_role: str,
) -> list[str]:
    capability_rows = connection.execute(
        text("""
            SELECT capability
            FROM user_capabilities
            WHERE user_id = :user_id
        """),
        {"user_id": user_id},
    ).mappings().all()

    capabilities = {
        row["capability"]
        for row in capability_rows
    }

    legacy_capability = {
        "farmer": "farmer",
        "supplier": "provider",
        "admin": "admin",
    }.get(user_role)

    if legacy_capability:
        capabilities.add(legacy_capability)

    return sorted(capabilities)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired sign-in token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_error

    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (InvalidTokenError, ValueError):
        raise credentials_error

    with engine.connect() as connection:
        user = connection.execute(
            text("""
                SELECT user_id, full_name, email, phone, user_role, signup_intent, created_at
                FROM users
                WHERE user_id = :user_id
            """),
            {"user_id": user_id},
        ).mappings().first()

    if not user:
        raise credentials_error

    return dict(user)


@app.get("/farmers/{farmer_id}/farms")
def get_farmer_farms(
    farmer_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farmer access is required.",
        )

    if current_user["user_id"] != farmer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own farm data.",
        )

    with engine.connect() as connection:
        farms = connection.execute(
            text("""
                SELECT farm_id, farm_name, location, total_area_acres
                FROM farms
                WHERE farmer_id = :farmer_id
                ORDER BY farm_name
            """),
            {"farmer_id": farmer_id},
        ).mappings().all()

    return [dict(farm) for farm in farms]


@app.get("/farmers/{farmer_id}/addresses")
def get_farmer_addresses(
    farmer_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farmer access is required.",
        )

    if current_user["user_id"] != farmer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own farm data.",
        )

    with engine.connect() as connection:
        addresses = connection.execute(
            text("""
                SELECT
                    address_id,
                    label,
                    address_line1,
                    village_or_city,
                    district,
                    state,
                    postal_code
                FROM addresses
                WHERE user_id = :farmer_id
                ORDER BY is_default DESC, address_id
            """),
            {"farmer_id": farmer_id},
        ).mappings().all()

    return [dict(address) for address in addresses]


@app.post("/bookings", deprecated=True)
def create_booking(
    booking: BookingCreate,
    current_user: dict = Depends(get_current_user),
):
    """Compatibility route that delegates to the transactional booking path."""
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Farmer access is required.",
        )

    if booking.farmer_id != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create bookings for your own account.",
        )

    if booking.requested_end_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The booking end time is required.",
        )

    return create_my_booking(
        CurrentUserBookingCreate(
            supplier_service_id=booking.supplier_service_id,
            farm_id=booking.farm_id,
            service_address_id=booking.service_address_id,
            requested_start_at=booking.requested_start_at,
            requested_end_at=booking.requested_end_at,
            quantity=booking.quantity,
            customer_notes=booking.customer_notes,
        ),
        current_user=current_user,
    )

# =========================================================
# ADMIN DASHBOARD
# =========================================================


@app.get("/provider/profile")
def get_provider_profile(
    current_user: dict = Depends(get_current_user),
):
    if not (has_provider_capability(current_user) or has_farmer_capability(current_user)):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    with engine.connect() as connection:
        profile = connection.execute(
            text("""
                SELECT
                    supplier_id,
                    business_name,
                    description,
                    business_registration_no,
                    gstin,
                    verified_at,
                    average_rating,
                    total_reviews,
                    is_active,
                    created_at
                FROM supplier_profiles
                WHERE supplier_id = :user_id
            """),
            {"user_id": current_user["user_id"]},
        ).mappings().first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Provider profile not found.",
        )

    return dict(profile)

@app.post("/provider/profile", status_code=status.HTTP_201_CREATED)
def create_provider_profile(
    profile: ProviderProfileCreate,
    current_user: dict = Depends(get_current_user),
):
    if not (has_provider_capability(current_user) or has_farmer_capability(current_user)):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    with engine.begin() as connection:
        existing_profile = connection.execute(
            text("""
                SELECT supplier_id
                FROM supplier_profiles
                WHERE supplier_id = :user_id
            """),
            {"user_id": current_user["user_id"]},
        ).first()

        if existing_profile:
            raise HTTPException(
                status_code=409,
                detail="Provider profile already exists.",
            )

        new_profile = connection.execute(
            text("""
                INSERT INTO supplier_profiles (
                    supplier_id,
                    business_name,
                    description,
                    business_registration_no,
                    gstin
                )
                VALUES (
                    :supplier_id,
                    :business_name,
                    :description,
                    :business_registration_no,
                    :gstin
                )
                RETURNING
                    supplier_id,
                    business_name,
                    description,
                    business_registration_no,
                    gstin,
                    verified_at,
                    average_rating,
                    total_reviews,
                    is_active,
                    created_at
            """),
            {
                "supplier_id": current_user["user_id"],
                "business_name": profile.business_name.strip(),
                "description": profile.description,
                "business_registration_no": profile.business_registration_no,
                "gstin": profile.gstin,
            },
        ).mappings().one()

        # Grant provider access to the same account in the profile transaction.
        connection.execute(
            text("""
                INSERT INTO user_capabilities (user_id, capability)
                VALUES (:user_id, 'provider')
                ON CONFLICT (user_id, capability) DO NOTHING
            """),
            {"user_id": current_user["user_id"]},
        )

    return dict(new_profile)


@app.put("/provider/profile")
def update_provider_profile(
    profile: ProviderProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    with engine.begin() as connection:
        updated_profile = connection.execute(
            text("""
                UPDATE supplier_profiles
                SET
                    business_name = :business_name,
                    description = :description,
                    business_registration_no = :business_registration_no,
                    gstin = :gstin
                WHERE supplier_id = :user_id
                RETURNING
                    supplier_id,
                    business_name,
                    description,
                    business_registration_no,
                    gstin,
                    verified_at,
                    average_rating,
                    total_reviews,
                    is_active,
                    created_at
            """),
            {
                "user_id": current_user["user_id"],
                "business_name": profile.business_name.strip(),
                "description": profile.description,
                "business_registration_no": profile.business_registration_no,
                "gstin": profile.gstin,
            },
        ).mappings().first()

    if not updated_profile:
        raise HTTPException(
            status_code=404,
            detail="Provider profile not found.",
        )

    return dict(updated_profile)



@app.get("/provider/documents")
def get_provider_documents(
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    with engine.connect() as connection:
        profile = connection.execute(
            text("""
                SELECT supplier_id
                FROM supplier_profiles
                WHERE supplier_id = :user_id
            """),
            {"user_id": current_user["user_id"]},
        ).first()

        if not profile:
            raise HTTPException(
                status_code=404,
                detail="Provider profile not found.",
            )

        documents = connection.execute(
            text("""
                SELECT
                    document_id,
                    document_type,
                    file_name,
                    file_url,
                    verification_status,
                    uploaded_at
                FROM documents
                WHERE user_id = :user_id
                  AND booking_id IS NULL
                ORDER BY uploaded_at DESC, document_id DESC
            """),
            {"user_id": current_user["user_id"]},
        ).mappings().all()

    return [
        serialize_provider_document(document)
        for document in documents
    ]


@app.post(
    "/provider/documents",
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_document(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    if request.headers.get("content-type", "").lower().startswith("application/json"):
        try:
            document = ProviderVerificationDocumentCreate.model_validate(
                await request.json()
            )
        except (ValidationError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid provider document request.")

        document_type = document.document_type.strip()
        file_name = Path(document.file_name.replace("\\", "/")).name.strip()
        file_url = document.file_url.strip()
    elif request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        form = await request.form()
        uploaded_file = form.get("file")
        document_type = str(form.get("document_type") or "").strip()
        file_name = Path(
            (getattr(uploaded_file, "filename", "") or "").replace("\\", "/")
        ).name.strip()
        if not uploaded_file or not file_name:
            raise HTTPException(status_code=400, detail="Choose a document file to upload.")

        extension = Path(file_name).suffix.lower()
        allowed_type = ALLOWED_DOCUMENT_FILE_TYPES.get(extension)
        if not allowed_type:
            raise HTTPException(status_code=400, detail="Only PDF, JPEG, and PNG documents can be uploaded.")
        expected_content_type, signature = allowed_type
        if (getattr(uploaded_file, "content_type", "") or "").lower() != expected_content_type:
            raise HTTPException(status_code=400, detail="The document file type does not match its extension.")
        content = await uploaded_file.read(MAX_DOCUMENT_UPLOAD_BYTES + 1)
        if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail=f"Document files must be no larger than {MAX_DOCUMENT_UPLOAD_MB} MB.")
        if not content or not content.startswith(signature):
            raise HTTPException(status_code=400, detail="The document file contents do not match its declared type.")

        storage_filename = f"{uuid4().hex}{extension}"
        storage_path = DOCUMENT_STORAGE_DIR / storage_filename
        file_url = f"{STORED_DOCUMENT_REFERENCE_PREFIX}{storage_filename}"
    else:
        raise HTTPException(status_code=415, detail="Submit a document file as multipart form data.")

    if not document_type or not file_name or not file_url or len(file_name) > 255:
        raise HTTPException(
            status_code=400,
            detail="Document type, file name, and file URL are required.",
        )

    if document_type not in PROVIDER_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a supported provider verification document type.",
        )

    stored_file = False
    try:
        if "storage_path" in locals():
            DOCUMENT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            with storage_path.open("xb") as output_file:
                output_file.write(content)
            stored_file = True

        with engine.begin() as connection:
            profile = connection.execute(
            text("""
                SELECT supplier_id
                FROM supplier_profiles
                WHERE supplier_id = :user_id
            """),
            {"user_id": current_user["user_id"]},
        ).first()

            if not profile:
                raise HTTPException(
                    status_code=404,
                    detail="Provider profile not found.",
                )

            new_document = connection.execute(
            text("""
                INSERT INTO documents (
                    user_id,
                    booking_id,
                    document_type,
                    file_name,
                    file_url,
                    verification_status
                )
                VALUES (
                    :user_id,
                    NULL,
                    :document_type,
                    :file_name,
                    :file_url,
                    'pending'
                )
                RETURNING
                    document_id,
                    document_type,
                    file_name,
                    file_url,
                    verification_status,
                    uploaded_at
            """),
            {
                "user_id": current_user["user_id"],
                "document_type": document_type,
                "file_name": file_name,
                "file_url": file_url,
            },
            ).mappings().one()
    except Exception:
        if stored_file:
            storage_path.unlink(missing_ok=True)
        raise

    return serialize_provider_document(new_document)


@app.get("/provider/documents/{document_id}/file")
def get_provider_document_file(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    is_admin = current_user["user_role"] == "admin"
    if not is_admin and not has_provider_capability(current_user):
        raise HTTPException(status_code=403, detail="Provider access is required.")

    with engine.connect() as connection:
        document = connection.execute(
            text("""
                SELECT d.user_id, d.file_name, d.file_url
                FROM documents d
                JOIN supplier_profiles sp ON sp.supplier_id = d.user_id
                WHERE d.document_id = :document_id
                  AND d.booking_id IS NULL
            """),
            {"document_id": document_id},
        ).mappings().first()

    if not document:
        raise HTTPException(status_code=404, detail="Provider document not found.")
    if not is_admin and document["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="You can only access your own provider documents.")
    if not document["file_url"].startswith(STORED_DOCUMENT_REFERENCE_PREFIX):
        raise HTTPException(status_code=404, detail="This legacy document reference has no uploaded file.")

    storage_filename = document["file_url"][len(STORED_DOCUMENT_REFERENCE_PREFIX):]
    storage_path = (DOCUMENT_STORAGE_DIR / storage_filename).resolve()
    if storage_path.parent != DOCUMENT_STORAGE_DIR or not storage_path.is_file():
        raise HTTPException(status_code=404, detail="Uploaded document file not found.")

    content_type = ALLOWED_DOCUMENT_FILE_TYPES.get(storage_path.suffix.lower(), (None,))[0]
    if not content_type:
        raise HTTPException(status_code=404, detail="Uploaded document file not found.")

    return FileResponse(
        storage_path,
        media_type=content_type,
        filename=document["file_name"],
        content_disposition_type="attachment",
    )


@app.get("/admin/dashboard")
def admin_dashboard(
    current_user: dict = Depends(get_current_user),
):
    # -----------------------------------------------------
    # ADMIN ACCESS ONLY
    # -----------------------------------------------------
    if current_user["user_role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )

    # -----------------------------------------------------
    # LOAD PLATFORM METRICS
    # -----------------------------------------------------
    with engine.connect() as connection:

        total_users = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM users
            """)
        ).scalar_one()

        total_farmers = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM users
                WHERE user_role = 'farmer'
            """)
        ).scalar_one()

        total_suppliers = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM users
                WHERE user_role = 'supplier'
            """)
        ).scalar_one()

        total_admins = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM users
                WHERE user_role = 'admin'
            """)
        ).scalar_one()

        active_services = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM supplier_services
                WHERE is_active = TRUE
            """)
        ).scalar_one()

        total_bookings = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM bookings
            """)
        ).scalar_one()

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------
    return {
        "total_users": total_users,
        "total_farmers": total_farmers,
        "total_suppliers": total_suppliers,
        "total_admins": total_admins,
        "active_services": active_services,
        "total_bookings": total_bookings,
    }


@app.get("/admin/provider-verification")
def get_provider_verification_queue(
    current_user: dict = Depends(get_current_user),
):
    if current_user["user_role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )

    with engine.connect() as connection:
        providers = connection.execute(
            text("""
                SELECT
                    sp.supplier_id AS provider_id,
                    u.full_name AS provider_name,
                    sp.business_name,
                    sp.description,
                    sp.verified_at,
                    sp.is_active,
                    COUNT(d.document_id) AS submitted_document_count,
                    COUNT(d.document_id) FILTER (
                        WHERE d.verification_status = 'verified'
                    ) AS verified_document_count,
                    COUNT(d.document_id) FILTER (
                        WHERE d.verification_status = 'pending'
                    ) AS pending_document_count,
                    COUNT(d.document_id) FILTER (
                        WHERE d.verification_status = 'rejected'
                    ) AS rejected_document_count
                FROM supplier_profiles sp
                JOIN users u
                    ON u.user_id = sp.supplier_id
                LEFT JOIN documents d
                    ON d.user_id = sp.supplier_id
                   AND d.booking_id IS NULL
                WHERE sp.verified_at IS NULL
                GROUP BY
                    sp.supplier_id,
                    u.full_name,
                    sp.business_name,
                    sp.description,
                    sp.verified_at,
                    sp.is_active,
                    sp.created_at
                ORDER BY sp.created_at DESC, sp.supplier_id DESC
            """)
        ).mappings().all()

    return [dict(provider) for provider in providers]


@app.get("/admin/provider-verification/{supplier_id}")
def get_provider_verification_detail(
    supplier_id: int,
    current_user: dict = Depends(get_current_user),
):
    if current_user["user_role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )

    with engine.connect() as connection:
        provider = connection.execute(
            text("""
                SELECT
                    sp.supplier_id AS provider_id,
                    u.full_name AS provider_name,
                    sp.business_name,
                    sp.description,
                    sp.business_registration_no,
                    sp.gstin,
                    sp.verified_at,
                    sp.is_active,
                    sp.created_at
                FROM supplier_profiles sp
                JOIN users u
                    ON u.user_id = sp.supplier_id
                WHERE sp.supplier_id = :supplier_id
            """),
            {"supplier_id": supplier_id},
        ).mappings().first()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found.",
            )

        documents = connection.execute(
            text("""
                SELECT
                    document_id,
                    document_type,
                    file_name,
                    file_url,
                    verification_status,
                    uploaded_at
                FROM documents
                WHERE user_id = :supplier_id
                  AND booking_id IS NULL
                ORDER BY uploaded_at DESC, document_id DESC
            """),
            {"supplier_id": supplier_id},
        ).mappings().all()

    return {
        "provider": dict(provider),
        "documents": [
            serialize_provider_document(document)
            for document in documents
        ],
    }


@app.put("/admin/documents/{document_id}/verify")
def verify_provider_document(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    if current_user["user_role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )

    with engine.begin() as connection:
        document = connection.execute(
            text("""
                SELECT d.document_id
                FROM documents d
                JOIN supplier_profiles sp
                    ON sp.supplier_id = d.user_id
                WHERE d.document_id = :document_id
                  AND d.booking_id IS NULL
                FOR UPDATE OF d
            """),
            {"document_id": document_id},
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider verification document not found.",
            )

        updated_document = connection.execute(
            text("""
                UPDATE documents
                SET verification_status = 'verified'
                WHERE document_id = :document_id
                RETURNING
                    document_id,
                    document_type,
                    file_name,
                    file_url,
                    verification_status,
                    uploaded_at
            """),
            {"document_id": document_id},
        ).mappings().one()

    return serialize_provider_document(updated_document)


@app.put("/admin/documents/{document_id}/reject")
def reject_provider_document(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    if current_user["user_role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )

    with engine.begin() as connection:
        document = connection.execute(
            text("""
                SELECT d.document_id
                FROM documents d
                JOIN supplier_profiles sp
                    ON sp.supplier_id = d.user_id
                WHERE d.document_id = :document_id
                  AND d.booking_id IS NULL
                FOR UPDATE OF d
            """),
            {"document_id": document_id},
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider verification document not found.",
            )

        updated_document = connection.execute(
            text("""
                UPDATE documents
                SET verification_status = 'rejected'
                WHERE document_id = :document_id
                RETURNING
                    document_id,
                    document_type,
                    file_name,
                    file_url,
                    verification_status,
                    uploaded_at
            """),
            {"document_id": document_id},
        ).mappings().one()

    return serialize_provider_document(updated_document)


@app.put("/admin/provider-verification/{supplier_id}/verify")
def verify_provider(
    supplier_id: int,
    current_user: dict = Depends(get_current_user),
):
    if current_user["user_role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )

    with engine.begin() as connection:
        provider = connection.execute(
            text("""
                SELECT supplier_id
                FROM supplier_profiles
                WHERE supplier_id = :supplier_id
                FOR UPDATE
            """),
            {"supplier_id": supplier_id},
        ).first()

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider profile not found.",
            )

        verified_documents = connection.execute(
            text("""
                SELECT document_id
                FROM documents
                WHERE user_id = :supplier_id
                  AND booking_id IS NULL
                  AND verification_status = 'verified'
                  AND document_type = ANY(:eligible_document_types)
                FOR UPDATE
            """),
            {
                "supplier_id": supplier_id,
                "eligible_document_types": list(
                    PROVIDER_VERIFICATION_ELIGIBLE_DOCUMENT_TYPES
                ),
            },
        ).all()

        if not verified_documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "A provider must have at least one verified "
                    "identity, vehicle/equipment RC, or service/trade "
                    "certificate document before provider verification."
                ),
            )

        updated_provider = connection.execute(
            text("""
                UPDATE supplier_profiles
                SET verified_at = CURRENT_TIMESTAMP
                WHERE supplier_id = :supplier_id
                RETURNING
                    supplier_id AS provider_id,
                    business_name,
                    verified_at,
                    is_active
            """),
            {"supplier_id": supplier_id},
        ).mappings().one()

    return dict(updated_provider)


def create_notification(
    connection,
    user_id: int,
    title: str,
    message: str,
    notification_type: str = "booking",
    related_booking_id: int | None = None,
):
    connection.execute(
        text("""
            INSERT INTO notifications (
                user_id,
                title,
                message,
                notification_type,
                related_booking_id,
                is_read,
                created_at
            )
            VALUES (
                :user_id,
                :title,
                :message,
                :notification_type,
                :related_booking_id,
                FALSE,
                CURRENT_TIMESTAMP
            )
        """),
        {
            "user_id": user_id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "related_booking_id": related_booking_id,
        },
    )

@app.get("/my/notifications")
def get_my_notifications(
    current_user: dict = Depends(get_current_user),
):
    with engine.connect() as connection:
        notifications = connection.execute(
            text("""
                SELECT
                    n.notification_id,
                    n.title,
                    n.message,
                    n.notification_type,
                    n.related_booking_id,
                    n.is_read,
                    n.created_at,

                    CASE
                        WHEN b.supplier_id = :user_id
                            THEN 'provider'
                        WHEN b.farmer_id = :user_id
                            THEN 'farmer'
                        ELSE NULL
                    END AS booking_context

                FROM notifications n

                LEFT JOIN bookings b
                    ON b.booking_id = n.related_booking_id

                WHERE n.user_id = :user_id

                ORDER BY n.created_at DESC, n.notification_id DESC
            """),
            {
                "user_id": current_user["user_id"],
            },
        ).mappings().all()

    return [dict(notification) for notification in notifications]

@app.put("/my/notifications/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
):
    with engine.begin() as connection:
        notification = connection.execute(
            text("""
                UPDATE notifications
                SET is_read = TRUE
                WHERE notification_id = :notification_id
                  AND user_id = :user_id
                RETURNING
                    notification_id,
                    title,
                    message,
                    is_read
            """),
            {
                "notification_id": notification_id,
                "user_id": current_user["user_id"],
            },
        ).mappings().first()

        if not notification:
            raise HTTPException(
                status_code=404,
                detail="Notification not found.",
            )

    return dict(notification)


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    role_for_intent = {'farmer':'farmer','provider':'supplier','field_officer':'member','landowner':'member'}
    role = role_for_intent.get(request.signup_intent, request.user_role)
    if role is None or (request.signup_intent and request.user_role and request.user_role != role):
        raise HTTPException(422, 'Choose one valid signup option.')
    if request.field_officer_application is not None and request.signup_intent != 'field_officer':
        raise HTTPException(422, 'Application details are only accepted for Field Officer signup.')

    email = request.email.strip().lower() if request.email else None
    phone = re.sub(r"[\s()+-]", "", request.phone or "") or None
    if not email and not phone:
        raise HTTPException(status_code=422, detail="Enter a mobile number or email address.")
    if phone and (not phone.isdigit() or not 7 <= len(phone) <= 15):
        raise HTTPException(status_code=422, detail="Enter a valid mobile number.")

    try:
        with engine.begin() as connection:
            existing_user = connection.execute(
                text("SELECT user_id FROM users WHERE LOWER(email) = :email OR regexp_replace(phone, '[[:space:]()+-]', '', 'g') = :phone"),
                {"email": email, "phone": phone},
            ).first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email or mobile number already exists.",
                )

            user = connection.execute(
                text("""
                    INSERT INTO users (
                        full_name, email, phone, password_hash, user_role, signup_intent
                    )
                    VALUES (
                        :full_name, :email, :phone, :password_hash, :user_role, :signup_intent
                    )
                    RETURNING user_id, full_name, email, user_role, signup_intent
                """),
                {
                    "full_name": request.full_name.strip(),
                    "email": email,
                    "phone": phone,
                    "password_hash": password_hash.hash(request.password),
                    "user_role": role,
                    "signup_intent": request.signup_intent,
                },
            ).mappings().one()

            if request.signup_intent == "field_officer":
                submit_application(connection, user["user_id"], request.field_officer_application or ApplicationFields())

            if role == "supplier":
                business_name = (
                    request.business_name.strip()
                    if request.business_name
                    else request.full_name.strip()
                )

                connection.execute(
                    text("""
                        INSERT INTO supplier_profiles (
                            supplier_id, business_name, description
                        )
                        VALUES (:supplier_id, :business_name, :description)
                    """),
                    {
                        "supplier_id": user["user_id"],
                        "business_name": business_name,
                        "description": "New supplier profile.",
                    },
                )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email or phone number is already in use.",
        )

    return {
        "message": "Account created successfully.",
        "user": dict(user),
    }


@app.post("/auth/login")
def login(request: LoginRequest):
    email = request.email.strip().lower() if request.email else None
    phone = re.sub(r"[\s()+-]", "", request.phone or "") or None
    if not email and not phone:
        raise HTTPException(status_code=422, detail="Enter a mobile number or email address.")
    if phone and (not phone.isdigit() or not 7 <= len(phone) <= 15):
        raise HTTPException(status_code=422, detail="Enter a valid mobile number.")

    with engine.connect() as connection:
        user = connection.execute(
            text("""
                SELECT user_id, full_name, email, password_hash, user_role, signup_intent
                FROM users
                WHERE (CAST(:phone AS TEXT) IS NULL AND LOWER(email) = :email)
                   OR (CAST(:phone AS TEXT) IS NOT NULL AND regexp_replace(phone, '[[:space:]()+-]', '', 'g') = :phone)
            """),
            {"email": email, "phone": phone},
        ).mappings().all()

        user = user[0] if len(user) == 1 else None
        if not user or not password_hash.verify(
            request.password,
            user["password_hash"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect mobile number, email or password.",
            )

        capabilities = get_effective_capabilities(
            connection,
            user["user_id"],
            user["user_role"],
        )

    access_token = create_access_token(
        user["user_id"],
        user["user_role"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "user_role": user["user_role"],
            "capabilities": capabilities,
            "signup_intent": user["signup_intent"],
        },
    }


@app.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    with engine.connect() as connection:
        capabilities = get_effective_capabilities(
            connection,
            current_user["user_id"],
            current_user["user_role"],
        )

    return {
        **current_user,
        "capabilities": capabilities,
    }
class DemoPaymentCreate(BaseModel):
    payment_method: Literal["upi", "card", "net_banking", "wallet"]


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    review_text: str | None = Field(default=None, max_length=1000)

class SupplierEquipmentServicesUpdate(BaseModel):
    service_ids: list[int]


@app.post("/my/bookings/{booking_id}/payment")
def pay_for_booking(
    booking_id: int,
    payment: DemoPaymentCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Farmer access is required.",
        )

    with engine.begin() as connection:
        booking = connection.execute(
            text("""
                SELECT
                    b.booking_id,
                    b.booking_number,
                    b.supplier_id,
                    b.status,
                    b.total_amount,
                    b.payment_status,
                    COALESCE(sp.business_name, u.full_name) AS supplier_name
                FROM bookings b
                JOIN supplier_profiles sp
                    ON sp.supplier_id = b.supplier_id
                JOIN users u
                    ON u.user_id = sp.supplier_id
                WHERE b.booking_id = :booking_id
                  AND b.farmer_id = :farmer_id
                FOR UPDATE
            """),
            {
                "booking_id": booking_id,
                "farmer_id": current_user["user_id"],
            },
        ).mappings().first()

        if not booking:
            raise HTTPException(
                status_code=404,
                detail="Booking not found.",
            )

        if booking["payment_status"] == "paid":
            raise HTTPException(
                status_code=400,
                detail="This booking has already been paid.",
            )

        if booking["status"] not in {
            "confirmed",
            "in_progress",
            "completed",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The supplier must confirm this booking "
                    "before payment."
                ),
            )

        transaction_id = (
            f"DEMO-PAY-{datetime.now():%Y%m%d%H%M%S%f}"
        )

        new_payment = connection.execute(
            text("""
                INSERT INTO payments (
                    booking_id,
                    payer_id,
                    amount,
                    payment_method,
                    provider,
                    provider_transaction_id,
                    status,
                    paid_at
                )
                VALUES (
                    :booking_id,
                    :payer_id,
                    :amount,
                    :payment_method,
                    'Demo Payment Gateway',
                    :transaction_id,
                    'paid',
                    CURRENT_TIMESTAMP
                )
                RETURNING
                    payment_id,
                    amount,
                    payment_method,
                    status,
                    paid_at
            """),
            {
                "booking_id": booking_id,
                "payer_id": current_user["user_id"],
                "amount": booking["total_amount"],
                "payment_method": payment.payment_method,
                "transaction_id": transaction_id,
            },
        ).mappings().one()

        connection.execute(
            text("""
                UPDATE bookings
                SET payment_status = 'paid',
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = :booking_id
            """),
            {
                "booking_id": booking_id,
            },
        )

        create_notification(
            connection=connection,
            user_id=booking["supplier_id"],
            title="Payment received",
            message=(
                f"Payment of ₹{booking['total_amount']:,.2f} "
                f"has been received for booking "
                f"{booking['booking_number']}."
            ),
            notification_type="payment",
            related_booking_id=booking["booking_id"],
        )

    return {
        "message": "Demo payment completed successfully.",
        "payment": dict(new_payment),
    }

@app.post("/my/bookings/{booking_id}/review", status_code=status.HTTP_201_CREATED)
def review_booking(
    booking_id: int,
    review: ReviewCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(status_code=403, detail="Farmer access is required.")

    with engine.begin() as connection:
        booking = connection.execute(
            text("""
                SELECT booking_id, supplier_id, status
                FROM bookings
                WHERE booking_id = :booking_id
                  AND farmer_id = :farmer_id
                FOR UPDATE
            """),
            {
                "booking_id": booking_id,
                "farmer_id": current_user["user_id"],
            },
        ).mappings().first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found.")

        if booking["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail="You can review a booking only after it is completed.",
            )

        existing_review = connection.execute(
            text("""
                SELECT review_id
                FROM reviews
                WHERE booking_id = :booking_id
                  AND reviewer_id = :reviewer_id
            """),
            {
                "booking_id": booking_id,
                "reviewer_id": current_user["user_id"],
            },
        ).first()

        if existing_review:
            raise HTTPException(
                status_code=400,
                detail="You have already reviewed this booking.",
            )

        new_review = connection.execute(
            text("""
                INSERT INTO reviews (
                    booking_id,
                    reviewer_id,
                    supplier_id,
                    rating,
                    review_text
                )
                VALUES (
                    :booking_id,
                    :reviewer_id,
                    :supplier_id,
                    :rating,
                    :review_text
                )
                RETURNING review_id, rating, review_text, created_at
            """),
            {
                "booking_id": booking_id,
                "reviewer_id": current_user["user_id"],
                "supplier_id": booking["supplier_id"],
                "rating": review.rating,
                "review_text": review.review_text,
            },
        ).mappings().one()

        rating_summary = connection.execute(
            text("""
                SELECT
                    ROUND(AVG(rating)::numeric, 2) AS average_rating,
                    COUNT(*) AS total_reviews
                FROM reviews
                WHERE supplier_id = :supplier_id
            """),
            {"supplier_id": booking["supplier_id"]},
        ).mappings().one()

        connection.execute(
            text("""
                UPDATE supplier_profiles
                SET average_rating = :average_rating,
                    total_reviews = :total_reviews
                WHERE supplier_id = :supplier_id
            """),
            {
                "supplier_id": booking["supplier_id"],
                "average_rating": rating_summary["average_rating"],
                "total_reviews": rating_summary["total_reviews"],
            },
        )

    return {
        "message": "Review submitted successfully.",
        "review": dict(new_review),
    }
class SupplierServiceCreate(BaseModel):
    category_id: int
    description: str | None = None
    pricing_unit: Literal["fixed", "hour", "day", "acre", "trip", "custom"]
    base_price: float | None = Field(default=None, ge=0)
    minimum_charge: float | None = Field(default=None, ge=0)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)


@app.get("/service-categories")
def list_service_categories():
    with engine.connect() as connection:
        categories = connection.execute(
            text("""
                SELECT
                    category_id,
                    parent_category_id,
                    category_name,
                    description
                FROM service_categories
                WHERE is_active = TRUE
                ORDER BY
                    COALESCE(parent_category_id, category_id),
                    parent_category_id NULLS FIRST,
                    category_name
            """)
        ).mappings().all()

    return [dict(category) for category in categories]



@app.get("/supplier/dashboard")
def supplier_dashboard(current_user: dict = Depends(get_current_user)):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )


    with engine.connect() as connection:
        profile = connection.execute(
            text("""
                SELECT
                    business_name,
                    description,
                    average_rating,
                    total_reviews,
                    is_active
                FROM supplier_profiles
                WHERE supplier_id = :supplier_id
            """),
            {"supplier_id": current_user["user_id"]},
        ).mappings().first()

        service_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM supplier_services
                WHERE supplier_id = :supplier_id
            """),
            {"supplier_id": current_user["user_id"]},
        ).scalar()

    return {
        "supplier": dict(profile) if profile else None,
        "service_count": service_count,
    }


@app.get("/supplier/services")
def get_my_supplier_services(
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    with engine.connect() as connection:
        services = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.service_name,
                    ss.description,
                    ss.pricing_unit,
                    ss.base_price,
                    ss.minimum_charge,
                    ss.estimated_duration_minutes,
                    ss.is_active,
                    sc.category_name,
                    parent.category_name AS parent_category_name
                FROM supplier_services ss
                JOIN service_categories sc
                    ON sc.category_id = ss.category_id
                LEFT JOIN service_categories parent
                    ON parent.category_id = sc.parent_category_id
                WHERE ss.supplier_id = :supplier_id
                ORDER BY ss.created_at DESC
            """),
            {"supplier_id": current_user["user_id"]},
        ).mappings().all()

    return [dict(service) for service in services]


@app.post("/supplier/services", status_code=status.HTTP_201_CREATED)
def create_supplier_service(
    service: SupplierServiceCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    # =========================================================
    # PRICING VALIDATION
    # =========================================================

    if service.pricing_unit == "custom" and service.base_price is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A custom-priced service should not have a base price.",
        )

    if service.pricing_unit != "custom" and service.base_price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A base price is required for this pricing unit.",
        )

    # =========================================================
    # CREATE SUPPLIER SERVICE
    # =========================================================

    with engine.begin() as connection:

        # Only an active CHILD service can be offered.
        category = connection.execute(
            text("""
                SELECT
                    category_id,
                    category_name,
                    parent_category_id
                FROM service_categories
                WHERE category_id = :category_id
                  AND is_active = TRUE
                  AND parent_category_id IS NOT NULL
            """),
            {"category_id": service.category_id},
        ).mappings().first()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found or is not available for supplier listing.",
            )

        # =====================================================
        # INSERT SERVICE
        # =====================================================

        new_service = connection.execute(
            text("""
                INSERT INTO supplier_services (
                    supplier_id,
                    category_id,
                    service_name,
                    description,
                    pricing_unit,
                    base_price,
                    minimum_charge,
                    estimated_duration_minutes
                )
                VALUES (
                    :supplier_id,
                    :category_id,
                    :service_name,
                    :description,
                    :pricing_unit,
                    :base_price,
                    :minimum_charge,
                    :estimated_duration_minutes
                )
                RETURNING
                    supplier_service_id,
                    service_name,
                    pricing_unit,
                    base_price,
                    is_active
            """),
            {
                "supplier_id": current_user["user_id"],
                "category_id": service.category_id,
                "service_name": category["category_name"],
                "description": service.description,
                "pricing_unit": service.pricing_unit,
                "base_price": service.base_price,
                "minimum_charge": service.minimum_charge,
                "estimated_duration_minutes": service.estimated_duration_minutes,
            },
        ).mappings().one()

        # =====================================================
        # RETURN COMPLETE SERVICE DETAILS
        # =====================================================

        complete_service = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.service_name,
                    ss.description,
                    ss.pricing_unit,
                    ss.base_price,
                    ss.minimum_charge,
                    ss.estimated_duration_minutes,
                    ss.is_active,
                    sc.category_name,
                    parent.category_name AS parent_category_name
                FROM supplier_services ss
                JOIN service_categories sc
                    ON sc.category_id = ss.category_id
                LEFT JOIN service_categories parent
                    ON parent.category_id = sc.parent_category_id
                WHERE ss.supplier_service_id = :supplier_service_id
            """),
            {
                "supplier_service_id": new_service["supplier_service_id"]
            },
        ).mappings().one()

    return dict(complete_service)

@app.get("/supplier/equipment/{equipment_id}/services")
def get_equipment_services(
    equipment_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    with engine.connect() as connection:

        # Verify equipment belongs to this supplier
        equipment = connection.execute(
            text("""
                SELECT equipment_id
                FROM equipment
                WHERE equipment_id = :equipment_id
                  AND supplier_id = :supplier_id
            """),
            {
                "equipment_id": equipment_id,
                "supplier_id": current_user["user_id"],
            },
        ).first()

        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found.",
            )

        services = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.service_name,
                    sc.category_name,
                    parent.category_name AS parent_category_name
                FROM service_equipment se
                JOIN supplier_services ss
                    ON ss.supplier_service_id = se.supplier_service_id
                JOIN service_categories sc
                    ON sc.category_id = ss.category_id
                LEFT JOIN service_categories parent
                    ON parent.category_id = sc.parent_category_id
                WHERE se.equipment_id = :equipment_id
                  AND ss.supplier_id = :supplier_id
                  AND ss.is_active = TRUE
                ORDER BY
                    parent.category_name NULLS LAST,
                    ss.service_name
            """),
            {
                "equipment_id": equipment_id,
                "supplier_id": current_user["user_id"],
            },
        ).mappings().all()

    return [dict(service) for service in services]

@app.put("/supplier/equipment/{equipment_id}/services")
def update_equipment_services(
    equipment_id: int,
    request: SupplierEquipmentServicesUpdate,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    # Remove duplicates while preserving the submitted order
    service_ids = list(dict.fromkeys(request.service_ids))

    with engine.begin() as connection:

        # =====================================================
        # VERIFY EQUIPMENT BELONGS TO SUPPLIER
        # =====================================================

        equipment = connection.execute(
            text("""
                SELECT equipment_id
                FROM equipment
                WHERE equipment_id = :equipment_id
                  AND supplier_id = :supplier_id
            """),
            {
                "equipment_id": equipment_id,
                "supplier_id": current_user["user_id"],
            },
        ).first()

        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found.",
            )

        # =====================================================
        # VERIFY ALL SERVICES BELONG TO SAME SUPPLIER
        # =====================================================

        if service_ids:
            valid_services = connection.execute(
                text("""
                    SELECT supplier_service_id
                    FROM supplier_services
                    WHERE supplier_service_id = ANY(:service_ids)
                      AND supplier_id = :supplier_id
                      AND is_active = TRUE
                """),
                {
                    "service_ids": service_ids,
                    "supplier_id": current_user["user_id"],
                },
            ).scalars().all()

            valid_service_ids = set(valid_services)

            invalid_service_ids = [
                service_id
                for service_id in service_ids
                if service_id not in valid_service_ids
            ]

            if invalid_service_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more selected services are invalid or do not belong to this supplier.",
                )

        # =====================================================
        # REPLACE EQUIPMENT-SERVICE LINKS
        # =====================================================

        connection.execute(
            text("""
                DELETE FROM service_equipment
                WHERE equipment_id = :equipment_id
            """),
            {
                "equipment_id": equipment_id,
            },
        )

        for service_id in service_ids:
            connection.execute(
                text("""
                    INSERT INTO service_equipment (
                        supplier_service_id,
                        equipment_id
                    )
                    VALUES (
                        :supplier_service_id,
                        :equipment_id
                    )
                """),
                {
                    "supplier_service_id": service_id,
                    "equipment_id": equipment_id,
                },
            )

        # =====================================================
        # RETURN UPDATED SERVICES
        # =====================================================

        services = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.service_name,
                    sc.category_name,
                    parent.category_name AS parent_category_name
                FROM service_equipment se
                JOIN supplier_services ss
                    ON ss.supplier_service_id = se.supplier_service_id
                JOIN service_categories sc
                    ON sc.category_id = ss.category_id
                LEFT JOIN service_categories parent
                    ON parent.category_id = sc.parent_category_id
                WHERE se.equipment_id = :equipment_id
                  AND ss.supplier_id = :supplier_id
                  AND ss.is_active = TRUE
                ORDER BY
                    parent.category_name NULLS LAST,
                    ss.service_name
            """),
            {
                "equipment_id": equipment_id,
                "supplier_id": current_user["user_id"],
            },
        ).mappings().all()

    return [dict(service) for service in services]

class BookingStatusUpdate(BaseModel):
    new_status: Literal["confirmed", "rejected", "in_progress", "completed", "cancelled"]
    notes: str | None = None


@app.get("/supplier/bookings")
def get_supplier_bookings(
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    with engine.connect() as connection:
        bookings = connection.execute(
            text("""
                SELECT
                    b.booking_id,
                    b.booking_number,
                    b.crop_task_id,b.crop_context_snapshot,
                    b.status,
                    b.requested_start_at,
                    b.requested_end_at,
                    b.total_amount,
                    b.payment_status,
                    b.customer_notes,
                    farmer.full_name AS farmer_name,
                    farmer.phone AS farmer_phone,
                    f.farm_name,
                    f.location AS farm_location,
                    STRING_AGG(bi.item_name, ', ' ORDER BY bi.item_name) AS service_names
                FROM bookings b
                JOIN users farmer ON farmer.user_id = b.farmer_id
                LEFT JOIN farms f ON f.farm_id = b.farm_id
                LEFT JOIN booking_items bi ON bi.booking_id = b.booking_id
                WHERE b.supplier_id = :supplier_id
                GROUP BY
                    b.booking_id,
                    b.booking_number,
                    b.status,
                    b.requested_start_at,
                    b.requested_end_at,
                    b.total_amount,
                    b.payment_status,
                    b.customer_notes,
                    farmer.full_name,
                    farmer.phone,
                    f.farm_name,
                    f.location
                ORDER BY b.created_at DESC
            """),
            {"supplier_id": current_user["user_id"]},
        ).mappings().all()

    return [dict(booking) for booking in bookings]


@app.put("/supplier/bookings/{booking_id}/status")
def update_supplier_booking_status(
    booking_id: int,
    update: BookingStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    allowed_transitions = {
        "pending": {"confirmed", "rejected", "cancelled"},
        "quoted": {"confirmed", "rejected", "cancelled"},
        "confirmed": {"in_progress", "cancelled"},
        "in_progress": {"completed"},
    }

    with engine.begin() as connection:
        # =====================================================
        # LOAD AND LOCK BOOKING
        # =====================================================

        booking = connection.execute(
            text("""
                SELECT
                    b.booking_id,
                    b.booking_number,
                    b.farmer_id,
                    b.status,
                    b.requested_start_at,
                    b.requested_end_at,

                    -- AgriConnect currently operates in India.
                    -- Convert database current time to India local time
                    -- because booking timestamps are timestamp without time zone.
                    CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata'
                        AS current_time,

                    COALESCE(
                        sp.business_name,
                        u.full_name
                    ) AS supplier_name

                FROM bookings b

                JOIN supplier_profiles sp
                    ON sp.supplier_id = b.supplier_id

                JOIN users u
                    ON u.user_id = sp.supplier_id

                WHERE b.booking_id = :booking_id
                  AND b.supplier_id = :supplier_id

                FOR UPDATE
            """),
            {
                "booking_id": booking_id,
                "supplier_id": current_user["user_id"],
            },
        ).mappings().first()

        # =====================================================
        # BOOKING NOT FOUND
        # =====================================================

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        # =====================================================
        # VALIDATE STATUS TRANSITION
        # =====================================================

        valid_next_statuses = allowed_transitions.get(
            booking["status"],
            set(),
        )

        if update.new_status not in valid_next_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot change a {booking['status']} booking to "
                    f"{update.new_status}."
                ),
            )

        # =====================================================
        # TIME-BASED RESTRICTION
        # confirmed -> in_progress
        # =====================================================

        if (
            booking["status"] == "confirmed"
            and update.new_status == "in_progress"
        ):
            if booking["requested_start_at"] > booking["current_time"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Work cannot be started before the scheduled "
                        "service start time."
                    ),
                )

        # =====================================================
        # TIME-BASED RESTRICTION
        # in_progress -> completed
        # =====================================================

        if (
            booking["status"] == "in_progress"
            and update.new_status == "completed"
        ):
            if booking["requested_end_at"] > booking["current_time"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Service cannot be marked completed before the "
                        "scheduled service end time."
                    ),
                )

        # =====================================================
        # UPDATE BOOKING STATUS
        # =====================================================

        updated_booking = connection.execute(
            text("""
                UPDATE bookings
                SET status = :new_status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = :booking_id
                RETURNING
                    booking_id,
                    booking_number,
                    status
            """),
            {
                "booking_id": booking_id,
                "new_status": update.new_status,
            },
        ).mappings().one()

        # =====================================================
        # STATUS HISTORY
        # =====================================================

        connection.execute(
            text("""
                INSERT INTO booking_status_history (
                    booking_id,
                    old_status,
                    new_status,
                    changed_by,
                    notes
                )
                VALUES (
                    :booking_id,
                    :old_status,
                    :new_status,
                    :changed_by,
                    :notes
                )
            """),
            {
                "booking_id": booking_id,
                "old_status": booking["status"],
                "new_status": update.new_status,
                "changed_by": current_user["user_id"],
                "notes": update.notes,
            },
        )

        # =====================================================
        # FARMER NOTIFICATION MESSAGES
        # =====================================================

        notification_messages = {
            "confirmed": (
                f"Your booking {booking['booking_number']} has been "
                f"confirmed by {booking['supplier_name']}."
            ),
            "rejected": (
                f"Your booking {booking['booking_number']} has been "
                f"rejected by {booking['supplier_name']}."
            ),
            "in_progress": (
                f"{booking['supplier_name']} has started work for "
                f"your booking {booking['booking_number']}."
            ),
            "completed": (
                f"{booking['supplier_name']} has completed the service "
                f"for your booking {booking['booking_number']}."
            ),
            "cancelled": (
                f"{booking['supplier_name']} has cancelled your "
                f"booking {booking['booking_number']}."
            ),
        }

        notification_titles = {
            "confirmed": "Booking confirmed",
            "rejected": "Booking rejected",
            "in_progress": "Work started",
            "completed": "Service completed",
            "cancelled": "Booking cancelled",
        }

        # =====================================================
        # DEBUG LOG
        # =====================================================

        print(
            "STATUS NOTIFICATION:",
            booking["booking_id"],
            booking["farmer_id"],
            booking["supplier_name"],
            update.new_status,
        )

        # =====================================================
        # CREATE FARMER NOTIFICATION
        # =====================================================

        create_notification(
            connection=connection,
            user_id=booking["farmer_id"],
            title=notification_titles[update.new_status],
            message=notification_messages[update.new_status],
            notification_type="booking",
            related_booking_id=booking["booking_id"],
        )

    # =========================================================
    # RESPONSE
    # =========================================================

    return {
        "message": "Booking status updated successfully.",
        **dict(updated_booking),
    }

class EquipmentCreate(BaseModel):
    equipment_category_id: int
    equipment_name: str = Field(min_length=3, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    description: str | None = None
    daily_rate: float | None = Field(default=None, ge=0)
    security_deposit: float = Field(default=0, ge=0)
    quantity_available: int = Field(default=1, ge=1)


@app.get("/equipment-categories")
def list_equipment_categories():
    with engine.connect() as connection:
        categories = connection.execute(
            text("""
                SELECT equipment_category_id, category_name, description
                FROM equipment_categories
                ORDER BY category_name
            """)
        ).mappings().all()

    return [dict(category) for category in categories]

def has_provider_capability(current_user: dict) -> bool:
    # Keep existing supplier accounts working during migration.
    if current_user["user_role"] == "supplier":
        return True

    with engine.connect() as connection:
        capability = connection.execute(
            text("""
                SELECT 1
                FROM user_capabilities
                WHERE user_id = :user_id
                  AND capability = 'provider'
                LIMIT 1
            """),
            {"user_id": current_user["user_id"]},
        ).first()

    return capability is not None


def has_farmer_capability(current_user: dict) -> bool:
    # Keep existing farmer accounts working during capability migration.
    if current_user["user_role"] == "farmer":
        return True

    with engine.connect() as connection:
        capability = connection.execute(
            text("""
                SELECT 1
                FROM user_capabilities
                WHERE user_id = :user_id
                  AND capability = 'farmer'
                LIMIT 1
            """),
            {"user_id": current_user["user_id"]},
        ).first()

    return capability is not None


@app.get("/supplier/equipment")
def get_my_equipment(current_user: dict = Depends(get_current_user)):
    if not has_provider_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    with engine.connect() as connection:
        equipment = connection.execute(
            text("""
                SELECT
                    e.equipment_id,
                    e.equipment_name,
                    e.brand,
                    e.model,
                    e.description,
                    e.daily_rate,
                    e.security_deposit,
                    e.quantity_available,
                    e.is_active,
                    ec.category_name
                FROM equipment e
                LEFT JOIN equipment_categories ec
                    ON ec.equipment_category_id = e.equipment_category_id
                WHERE e.supplier_id = :supplier_id
                ORDER BY e.created_at DESC
            """),
            {"supplier_id": current_user["user_id"]},
        ).mappings().all()

    return [dict(item) for item in equipment]

@app.post("/supplier/equipment", status_code=status.HTTP_201_CREATED)
def create_equipment(
    equipment: EquipmentCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Provider access is required.",
        )

    with engine.begin() as connection:
        category = connection.execute(
            text("""
                SELECT equipment_category_id
                FROM equipment_categories
                WHERE equipment_category_id = :category_id
            """),
            {"category_id": equipment.equipment_category_id},
        ).first()

        if not category:
            raise HTTPException(
                status_code=404,
                detail="Equipment category not found.",
            )

        new_equipment = connection.execute(
            text("""
                INSERT INTO equipment (
                    supplier_id,
                    equipment_category_id,
                    equipment_name,
                    brand,
                    model,
                    description,
                    daily_rate,
                    security_deposit,
                    quantity_available
                )
                VALUES (
                    :supplier_id,
                    :equipment_category_id,
                    :equipment_name,
                    :brand,
                    :model,
                    :description,
                    :daily_rate,
                    :security_deposit,
                    :quantity_available
                )
                RETURNING
                    equipment_id,
                    equipment_name,
                    daily_rate,
                    quantity_available,
                    is_active
            """),
            {
                "supplier_id": current_user["user_id"],
                "equipment_category_id": equipment.equipment_category_id,
                "equipment_name": equipment.equipment_name,
                "brand": equipment.brand,
                "model": equipment.model,
                "description": equipment.description,
                "daily_rate": equipment.daily_rate,
                "security_deposit": equipment.security_deposit,
                "quantity_available": equipment.quantity_available,
            },
        ).mappings().one()

    return dict(new_equipment)


class AvailabilityCreate(BaseModel):
    supplier_service_id: int | None = None
    equipment_id: int | None = None
    date: datetime
    hours: list[int]
    capacity: int = Field(default=1, ge=1)
    status: Literal["available", "blocked", "unavailable"] = "available"


@app.get("/supplier/availability")
def get_supplier_availability(
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    with engine.connect() as connection:
        slots = connection.execute(
            text("""
                SELECT
                    a.availability_slot_id,
                    a.starts_at,
                    a.ends_at,
                    a.capacity,
                    a.status,

                    COALESCE(SUM(
                        CASE
                            WHEN b.status NOT IN ('cancelled', 'rejected')
                            THEN r.reserved_quantity
                            ELSE 0
                        END
                    ), 0) AS reserved_quantity,

                    a.capacity - COALESCE(SUM(
                        CASE
                            WHEN b.status NOT IN ('cancelled', 'rejected')
                            THEN r.reserved_quantity
                            ELSE 0
                        END
                    ), 0) AS remaining_capacity,

                    CASE
                        WHEN a.supplier_service_id IS NOT NULL
                            THEN 'service'
                        ELSE 'equipment'
                    END AS item_type,

                    COALESCE(
                        ss.service_name,
                        e.equipment_name
                    ) AS item_name

                FROM availability_slots a

                LEFT JOIN supplier_services ss
                    ON ss.supplier_service_id = a.supplier_service_id

                LEFT JOIN equipment e
                    ON e.equipment_id = a.equipment_id

                LEFT JOIN booking_slot_reservations r
                    ON r.availability_slot_id = a.availability_slot_id

                LEFT JOIN bookings b
                    ON b.booking_id = r.booking_id

                WHERE ss.supplier_id = :supplier_id
                   OR e.supplier_id = :supplier_id

                GROUP BY
                    a.availability_slot_id,
                    a.starts_at,
                    a.ends_at,
                    a.capacity,
                    a.status,
                    a.supplier_service_id,
                    e.equipment_id,
                    ss.service_name,
                    e.equipment_name

                HAVING
                    a.capacity - COALESCE(SUM(
                        CASE
                            WHEN b.status NOT IN ('cancelled', 'rejected')
                            THEN r.reserved_quantity
                            ELSE 0
                        END
                    ), 0) > 0

                ORDER BY a.starts_at DESC
            """),
            {
                "supplier_id": current_user["user_id"],
            },
        ).mappings().all()

    return [dict(slot) for slot in slots]

@app.get("/supplier-services/{supplier_service_id}/availability")
def get_supplier_service_availability(
    supplier_service_id: int,
    date: str,
):
    try:
        selected_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Date must be in YYYY-MM-DD format.",
        )

    with engine.connect() as connection:
        service = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.service_name,
                    ss.base_price,
                    ss.pricing_unit,
                    sp.supplier_id,
                    COALESCE(
                        sp.business_name,
                        u.full_name
                    ) AS supplier_name,
                    COALESCE(
                        sp.average_rating,
                        0
                    ) AS average_rating
                FROM supplier_services ss
                JOIN supplier_profiles sp
                    ON sp.supplier_id = ss.supplier_id
                JOIN users u
                    ON u.user_id = sp.supplier_id
                WHERE ss.supplier_service_id = :supplier_service_id
                  AND ss.is_active = TRUE
                  AND sp.is_active = TRUE
                  AND sp.verified_at IS NOT NULL
            """),
            {
                "supplier_service_id": supplier_service_id,
            },
        ).mappings().first()

        if not service:
            raise HTTPException(
                status_code=404,
                detail="Supplier service not found.",
            )

        slots = connection.execute(
            text("""
                SELECT
                    a.availability_slot_id,
                    a.starts_at,
                    a.ends_at,
                    a.capacity,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN b.status NOT IN (
                                    'cancelled',
                                    'rejected'
                                )
                                THEN r.reserved_quantity
                                ELSE 0
                            END
                        ),
                        0
                    ) AS reserved_quantity,

                    a.capacity -
                    COALESCE(
                        SUM(
                            CASE
                                WHEN b.status NOT IN (
                                    'cancelled',
                                    'rejected'
                                )
                                THEN r.reserved_quantity
                                ELSE 0
                            END
                        ),
                        0
                    ) AS remaining_capacity

                FROM availability_slots a

                LEFT JOIN booking_slot_reservations r
                    ON r.availability_slot_id =
                       a.availability_slot_id

                LEFT JOIN bookings b
                    ON b.booking_id = r.booking_id

                WHERE a.supplier_service_id =
                      :supplier_service_id

                  AND a.status = 'available'

                  AND a.starts_at >= :date_start

                  AND a.starts_at < :date_end

                GROUP BY
                    a.availability_slot_id,
                    a.starts_at,
                    a.ends_at,
                    a.capacity

                HAVING
                    a.capacity -
                    COALESCE(
                        SUM(
                            CASE
                                WHEN b.status NOT IN (
                                    'cancelled',
                                    'rejected'
                                )
                                THEN r.reserved_quantity
                                ELSE 0
                            END
                        ),
                        0
                    ) > 0

                ORDER BY a.starts_at
            """),
            {
                "supplier_service_id": supplier_service_id,
                "date_start": selected_date,
                "date_end": selected_date + timedelta(days=1),
            },
        ).mappings().all()

    return [
        {
            **dict(service),
            **dict(slot),
        }
        for slot in slots
    ]

@app.post("/supplier/availability", status_code=status.HTTP_201_CREATED)
def create_availability_slots(
    slot: AvailabilityCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_provider_capability(current_user):
        raise HTTPException(
        status_code=403,
        detail="Provider access is required.",
    )

    has_service = slot.supplier_service_id is not None
    has_equipment = slot.equipment_id is not None

    if has_service == has_equipment:
        raise HTTPException(
            status_code=400,
            detail="Choose exactly one service or one equipment item.",
        )

    if not slot.hours:
        raise HTTPException(
            status_code=400,
            detail="Select at least one available hour.",
        )

    if slot.capacity < 1:
        raise HTTPException(
            status_code=400,
            detail="Capacity must be at least 1.",
        )

    # Validate that every selected value represents the start
    # of a one-hour slot.
    if any(hour < 0 or hour > 23 for hour in slot.hours):
        raise HTTPException(
            status_code=400,
            detail="Hours must be between 0 and 23.",
        )

    # Remove duplicates while preserving order.
    selected_hours = sorted(set(slot.hours))
     # ---------------------------------------------------------
    # Validate that every requested slot is in the future.
    # ---------------------------------------------------------
    now = datetime.now()

    for hour in selected_hours:
        starts_at = slot.date.replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0,
        )

        if starts_at <= now:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The selected time {starts_at.strftime('%d-%m-%Y %I:%M %p')} "
                    "is in the past. Please select a future date and time."
                ),
            )

    with engine.begin() as connection:

        # ---------------------------------------------------------
        # 1. Verify that the selected service/equipment belongs
        #    to the logged-in supplier.
        # ---------------------------------------------------------
        if has_service:
            item = connection.execute(
                text("""
                    SELECT
                        supplier_service_id,
                        service_name
                    FROM supplier_services
                    WHERE supplier_service_id = :item_id
                      AND supplier_id = :supplier_id
                """),
                {
                    "item_id": slot.supplier_service_id,
                    "supplier_id": current_user["user_id"],
                },
            ).mappings().first()

            if not item:
                raise HTTPException(
                    status_code=404,
                    detail="The selected service was not found.",
                )

        else:
            item = connection.execute(
                text("""
                    SELECT
                        equipment_id,
                        equipment_name
                    FROM equipment
                    WHERE equipment_id = :item_id
                      AND supplier_id = :supplier_id
                """),
                {
                    "item_id": slot.equipment_id,
                    "supplier_id": current_user["user_id"],
                },
            ).mappings().first()

            if not item:
                raise HTTPException(
                    status_code=404,
                    detail="The selected equipment was not found.",
                )

        # ---------------------------------------------------------
        # 2. Check all selected hours BEFORE inserting anything.
        #
        #    This gives us all-or-nothing behavior.
        #    If even one selected hour conflicts, no slots are
        #    created.
        # ---------------------------------------------------------
        conflicting_hours = []

        for hour in selected_hours:
            starts_at = slot.date.replace(
                hour=hour,
                minute=0,
                second=0,
                microsecond=0,
            )
            ends_at = starts_at + timedelta(hours=1)

            conflicting_slot = connection.execute(
                text("""
                    SELECT availability_slot_id
                    FROM availability_slots
                    WHERE (
                        supplier_service_id = :service_id
                        OR equipment_id = :equipment_id
                    )
                    AND starts_at < :ends_at
                    AND ends_at > :starts_at
                    AND status = 'available'
                """),
                {
                    "service_id": slot.supplier_service_id,
                    "equipment_id": slot.equipment_id,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                },
            ).first()

            if conflicting_slot:
                conflicting_hours.append(hour)

        if conflicting_hours:
            formatted_hours = ", ".join(
                f"{hour:02d}:00"
                for hour in conflicting_hours
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    f"These hours already have an available slot: "
                    f"{formatted_hours}."
                ),
            )

        # ---------------------------------------------------------
        # 3. Create one availability row per selected hour.
        # ---------------------------------------------------------
        created_slots = []

        for hour in selected_hours:
            starts_at = slot.date.replace(
                hour=hour,
                minute=0,
                second=0,
                microsecond=0,
            )
            ends_at = starts_at + timedelta(hours=1)

            new_slot = connection.execute(
                text("""
                    INSERT INTO availability_slots (
                        supplier_service_id,
                        equipment_id,
                        starts_at,
                        ends_at,
                        capacity,
                        status
                    )
                    VALUES (
                        :supplier_service_id,
                        :equipment_id,
                        :starts_at,
                        :ends_at,
                        :capacity,
                        'available'
                    )
                    RETURNING
                        availability_slot_id,
                        supplier_service_id,
                        equipment_id,
                        starts_at,
                        ends_at,
                        capacity,
                        status
                """),
                {
                    "supplier_service_id": slot.supplier_service_id,
                    "equipment_id": slot.equipment_id,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "capacity": slot.capacity,
                },
            ).mappings().one()

            created_slots.append(dict(new_slot))

    return {
        "message": (
            f"{len(created_slots)} availability slot(s) "
            "created successfully."
        ),
        "slots": created_slots,
    }


class FarmCreate(BaseModel):
    farm_name: str = Field(min_length=2, max_length=150)
    location: str = Field(min_length=2, max_length=255)
    total_area_acres: float | None = Field(default=None, gt=0)

class FarmPlotCreate(BaseModel):
    farm_id: int
    plot_name: str = Field(min_length=1, max_length=150)
    area_acres: float | None = Field(default=None, gt=0)
    soil_type: str | None = Field(default=None, max_length=100)
    irrigation_type: str | None = Field(default=None, max_length=100)

class FarmCropCreate(BaseModel):
    farm_id: int
    plot_id: int
    crop_id: int
    season: str | None = Field(default=None, max_length=100)
    planted_on: date | None = None
    expected_harvest_on: date | None = None


class AddressCreate(BaseModel):
    label: str = Field(default="Primary", max_length=50)
    address_line1: str = Field(min_length=2, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    village_or_city: str = Field(min_length=2, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool = False


@app.post("/farms", status_code=status.HTTP_201_CREATED)
def create_farm(
    farm: FarmCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only farmers can create farms.",
        )

    with engine.begin() as connection:
        new_farm = connection.execute(
            text("""
                INSERT INTO farms (
                    farmer_id, farm_name, location, total_area_acres
                )
                VALUES (
                    :farmer_id, :farm_name, :location, :total_area_acres
                )
                RETURNING farm_id, farm_name, location, total_area_acres
            """),
            {
                "farmer_id": current_user["user_id"],
                "farm_name": farm.farm_name,
                "location": farm.location,
                "total_area_acres": farm.total_area_acres,
            },
        ).mappings().one()

    return dict(new_farm)


@app.post("/addresses", status_code=status.HTTP_201_CREATED)
def create_address(
    address: AddressCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only farmers can create service addresses.",
        )

    with engine.begin() as connection:
        existing_address_count = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM addresses
                WHERE user_id = :user_id
            """),
            {"user_id": current_user["user_id"]},
        ).scalar()

        should_be_default = address.is_default or existing_address_count == 0

        if should_be_default:
            connection.execute(
                text("""
                    UPDATE addresses
                    SET is_default = FALSE
                    WHERE user_id = :user_id
                """),
                {"user_id": current_user["user_id"]},
            )

        new_address = connection.execute(
            text("""
                INSERT INTO addresses (
                    user_id, label, address_line1, address_line2,
                    village_or_city, district, state, postal_code, is_default
                )
                VALUES (
                    :user_id, :label, :address_line1, :address_line2,
                    :village_or_city, :district, :state, :postal_code,
                    :is_default
                )
                RETURNING
                    address_id, label, address_line1, village_or_city,
                    district, state, postal_code, is_default
            """),
            {
                "user_id": current_user["user_id"],
                "label": address.label,
                "address_line1": address.address_line1,
                "address_line2": address.address_line2,
                "village_or_city": address.village_or_city,
                "district": address.district,
                "state": address.state,
                "postal_code": address.postal_code,
                "is_default": should_be_default,
            },
        ).mappings().one()

    return dict(new_address)


class CurrentUserBookingCreate(BaseModel):
    crop_task_id: int | None = Field(default=None, gt=0)
    crop_request_key: UUID | None = None
    supplier_service_id: int
    farm_id: int | None = None
    service_address_id: int | None = None
    requested_start_at: datetime
    requested_end_at: datetime | None = None
    quantity: float = Field(gt=0)
    customer_notes: str | None = None
class BookingRescheduleRequest(BaseModel):
    requested_start_at: datetime
    requested_end_at: datetime
@app.post("/my/bookings/{booking_id}/reschedule")
def reschedule_my_booking(
    booking_id: int,
    request: BookingRescheduleRequest,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only farmers can reschedule bookings.",
        )

    farmer_id = current_user["user_id"]

    # ---------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------

    if request.requested_end_at <= request.requested_start_at:
        raise HTTPException(
            status_code=400,
            detail="The new end time must be after the new start time.",
        )

    duration = (
        request.requested_end_at
        - request.requested_start_at
    )

    # New booking must consist of complete hourly slots.
    if duration.total_seconds() % 3600 != 0:
        raise HTTPException(
            status_code=400,
            detail="The new booking must use complete 1-hour slots.",
        )

    # Start and end must align with hourly slots.
    if (
        request.requested_start_at.minute != 0
        or request.requested_start_at.second != 0
        or request.requested_start_at.microsecond != 0
        or request.requested_end_at.minute != 0
        or request.requested_end_at.second != 0
        or request.requested_end_at.microsecond != 0
    ):
        raise HTTPException(
            status_code=400,
            detail="The new booking must start and end on an exact hour.",
        )

    with engine.begin() as connection:

        # ---------------------------------------------------------
        # 1. Lock the booking
        # ---------------------------------------------------------

        booking = connection.execute(
            text("""
                SELECT
                    b.booking_id,
                    b.booking_number,
                    b.farmer_id,
                    b.supplier_id,
                    b.status,
                    b.requested_start_at,
                    b.requested_end_at,
                    bi.supplier_service_id,
                    bi.quantity,
                    COALESCE(sp.business_name, u.full_name)
                        AS supplier_name,
                    ss.service_name
                FROM bookings b
                JOIN booking_items bi
                    ON bi.booking_id = b.booking_id
                JOIN supplier_profiles sp
                    ON sp.supplier_id = b.supplier_id
                JOIN users u
                    ON u.user_id = sp.supplier_id
                JOIN supplier_services ss
                    ON ss.supplier_service_id =
                       bi.supplier_service_id
                WHERE b.booking_id = :booking_id
                  AND b.farmer_id = :farmer_id
                FOR UPDATE
            """),
            {
                "booking_id": booking_id,
                "farmer_id": farmer_id,
            },
        ).mappings().first()

        if not booking:
            raise HTTPException(
                status_code=404,
                detail="Booking not found.",
            )

        # ---------------------------------------------------------
        # 2. Validate booking status
        # ---------------------------------------------------------

        if booking["status"] not in (
            "pending",
            "quoted",
            "confirmed",
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Booking cannot be rescheduled when its "
                    f"status is '{booking['status']}'."
                ),
            )

        # ---------------------------------------------------------
        # 3. Make sure the NEW time is in the future
        #
        # Database booking timestamps are timestamp without
        # time zone, so compare against India local time.
        # ---------------------------------------------------------

        current_time = connection.execute(
            text("""
                SELECT
                    CURRENT_TIMESTAMP
                    AT TIME ZONE 'Asia/Kolkata'
                    AS current_time
            """)
        ).scalar_one()

        if request.requested_start_at <= current_time:
            raise HTTPException(
                status_code=400,
                detail="The new booking time must be in the future.",
            )

        # ---------------------------------------------------------
        # 4. Determine original booking duration
        # ---------------------------------------------------------

        original_duration = (
            booking["requested_end_at"]
            - booking["requested_start_at"]
        )

        if original_duration.total_seconds() % 3600 != 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This booking cannot be rescheduled because "
                    "its existing duration is not a complete "
                    "number of hours."
                ),
            )

        original_hours = int(
            original_duration.total_seconds() // 3600
        )

        new_duration = (
            request.requested_end_at
            - request.requested_start_at
        )

        new_hours = int(
            new_duration.total_seconds() // 3600
        )

        # ---------------------------------------------------------
        # 5. New duration must match original duration
        # ---------------------------------------------------------

        if new_hours != original_hours:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"This booking is {original_hours} hour(s) "
                    f"long. Please select exactly "
                    f"{original_hours} consecutive hour(s) "
                    "for rescheduling."
                ),
            )

        # ---------------------------------------------------------
        # 6. Prevent rescheduling to the same time
        # ---------------------------------------------------------

        if (
            booking["requested_start_at"]
            == request.requested_start_at
            and
            booking["requested_end_at"]
            == request.requested_end_at
        ):
            raise HTTPException(
                status_code=400,
                detail="The new time is the same as the current booking time.",
            )

        # ---------------------------------------------------------
        # 7. Generate all required hourly start times
        # ---------------------------------------------------------

        required_starts = []

        slot_start = request.requested_start_at

        while slot_start < request.requested_end_at:
            required_starts.append(slot_start)
            slot_start += timedelta(hours=1)

        # ---------------------------------------------------------
        # 8. Find and LOCK every new availability slot
        #
        # They must belong to the same supplier service.
        # ---------------------------------------------------------

        new_slots = connection.execute(
            text("""
                SELECT
                    a.availability_slot_id,
                    a.starts_at,
                    a.ends_at,
                    a.capacity
                FROM availability_slots a
                WHERE a.supplier_service_id =
                      :supplier_service_id
                  AND a.status = 'available'
                  AND a.starts_at >= :requested_start_at
                  AND a.ends_at <= :requested_end_at
                ORDER BY a.starts_at
                FOR UPDATE
            """),
            {
                "supplier_service_id":
                    booking["supplier_service_id"],
                "requested_start_at":
                    request.requested_start_at,
                "requested_end_at":
                    request.requested_end_at,
            },
        ).mappings().all()

        # ---------------------------------------------------------
        # 9. Verify EVERY required hourly slot exists
        # ---------------------------------------------------------

        slot_by_start = {
            slot["starts_at"]: slot
            for slot in new_slots
        }

        missing_slots = [
            slot_start
            for slot_start in required_starts
            if slot_start not in slot_by_start
        ]

        if missing_slots:
            missing_text = ", ".join(
                str(slot)
                for slot in missing_slots
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "The selected period is not completely "
                    f"available. Missing slot(s): {missing_text}"
                ),
            )

        # ---------------------------------------------------------
        # 10. Check capacity of EVERY new slot
        #
        # Exclude the current booking because its existing
        # reservation will be moved.
        # ---------------------------------------------------------

        quantity = Decimal(
            str(booking["quantity"])
        )

        for slot_start in required_starts:

            slot = slot_by_start[slot_start]

            reserved_quantity = connection.execute(
                text("""
                    SELECT COALESCE(
                        SUM(r.reserved_quantity),
                        0
                    )
                    FROM booking_slot_reservations r
                    JOIN bookings b
                        ON b.booking_id = r.booking_id
                    WHERE r.availability_slot_id =
                          :availability_slot_id
                      AND r.booking_id <> :booking_id
                      AND b.status NOT IN (
                          'cancelled',
                          'rejected'
                      )
                """),
                {
                    "availability_slot_id":
                        slot["availability_slot_id"],
                    "booking_id": booking_id,
                },
            ).scalar_one()

            if (
                Decimal(str(reserved_quantity))
                + quantity
                > Decimal(str(slot["capacity"]))
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"The slot "
                        f"{slot['starts_at']} - "
                        f"{slot['ends_at']} does not have "
                        "enough remaining capacity."
                    ),
                )

        # ---------------------------------------------------------
        # 11. Get existing reservations
        # ---------------------------------------------------------

        old_reservations = connection.execute(
            text("""
                SELECT
                    availability_slot_id,
                    reserved_quantity
                FROM booking_slot_reservations
                WHERE booking_id = :booking_id
                ORDER BY availability_slot_id
                FOR UPDATE
            """),
            {
                "booking_id": booking_id,
            },
        ).mappings().all()

        if len(old_reservations) != original_hours:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The booking reservation data is inconsistent. "
                    "Rescheduling cannot be completed."
                ),
            )

        # ---------------------------------------------------------
        # 12. Delete OLD reservations
        #
        # This happens only after all NEW slots have been
        # successfully locked and capacity verified.
        #
        # Because everything is inside engine.begin(), if anything
        # below fails, the entire transaction rolls back.
        # ---------------------------------------------------------

        connection.execute(
            text("""
                DELETE FROM booking_slot_reservations
                WHERE booking_id = :booking_id
            """),
            {
                "booking_id": booking_id,
            },
        )

        # ---------------------------------------------------------
        # 13. Create NEW reservations
        # ---------------------------------------------------------

        for slot_start in required_starts:

            slot = slot_by_start[slot_start]

            connection.execute(
                text("""
                    INSERT INTO booking_slot_reservations (
                        booking_id,
                        availability_slot_id,
                        reserved_quantity
                    )
                    VALUES (
                        :booking_id,
                        :availability_slot_id,
                        :reserved_quantity
                    )
                """),
                {
                    "booking_id": booking_id,
                    "availability_slot_id":
                        slot["availability_slot_id"],
                    "reserved_quantity": quantity,
                },
            )

        # ---------------------------------------------------------
        # 14. Update booking schedule
        # ---------------------------------------------------------

        connection.execute(
            text("""
                UPDATE bookings
                SET requested_start_at = :requested_start_at,
                    requested_end_at = :requested_end_at,
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = :booking_id
            """),
            {
                "requested_start_at":
                    request.requested_start_at,
                "requested_end_at":
                    request.requested_end_at,
                "booking_id": booking_id,
            },
        )

        # ---------------------------------------------------------
        # 15. Update booking item schedule
        # ---------------------------------------------------------

        connection.execute(
            text("""
                UPDATE booking_items
                SET scheduled_start_at = :scheduled_start_at,
                    scheduled_end_at = :scheduled_end_at
                WHERE booking_id = :booking_id
            """),
            {
                "scheduled_start_at":
                    request.requested_start_at,
                "scheduled_end_at":
                    request.requested_end_at,
                "booking_id": booking_id,
            },
        )

        # ---------------------------------------------------------
        # 16. Record reschedule history
        # ---------------------------------------------------------

        history_notes = (
            "Booking rescheduled by farmer. "
            f"Previous time: "
            f"{booking['requested_start_at']} - "
            f"{booking['requested_end_at']}. "
            f"New time: "
            f"{request.requested_start_at} - "
            f"{request.requested_end_at}."
        )

        connection.execute(
            text("""
                INSERT INTO booking_status_history (
                    booking_id,
                    old_status,
                    new_status,
                    changed_by,
                    notes
                )
                VALUES (
                    :booking_id,
                    :status,
                    :status,
                    :farmer_id,
                    :notes
                )
            """),
            {
                "booking_id": booking_id,
                "status": booking["status"],
                "farmer_id": farmer_id,
                "notes": history_notes,
            },
        )

        # ---------------------------------------------------------
        # 17. Notify supplier
        # ---------------------------------------------------------

        create_notification(
            connection=connection,
            user_id=booking["supplier_id"],
            title="Booking rescheduled",
            message=(
                f"Booking {booking['booking_number']} for "
                f"{booking['service_name']} has been rescheduled "
                f"by the farmer. "
                f"New time: "
                f"{request.requested_start_at} - "
                f"{request.requested_end_at}."
            ),
            notification_type="booking",
            related_booking_id=booking_id,
        )

    return {
        "message": "Booking rescheduled successfully.",
        "booking_id": booking["booking_id"],
        "booking_number": booking["booking_number"],
        "status": booking["status"],
        "old_start_at": booking["requested_start_at"],
        "old_end_at": booking["requested_end_at"],
        "new_start_at": request.requested_start_at,
        "new_end_at": request.requested_end_at,
        "duration_hours": new_hours,
    }

@app.get("/crops")
def get_crops(
    current_user: dict = Depends(get_current_user),
):
    with engine.connect() as connection:
        crops = connection.execute(
            text("""
                SELECT
                    crop_id,
                    crop_name,
                    scientific_name,
                    crop_group,
                    lifecycle_type,
                    harvest_pattern
                FROM crops
                ORDER BY crop_name
            """)
        ).mappings().all()

    return [dict(crop) for crop in crops]

@app.get("/my/farms")
def get_my_farms(current_user: dict = Depends(get_current_user)):
    if not has_farmer_capability(current_user):
        raise HTTPException(status_code=403, detail="Farmer access is required.")

    with engine.connect() as connection:
        farms = connection.execute(
            text("""
                SELECT farm_id, farm_name, location, total_area_acres
                FROM farms
                WHERE farmer_id = :farmer_id
                ORDER BY farm_name
            """),
            {"farmer_id": current_user["user_id"]},
        ).mappings().all()

    return [dict(farm) for farm in farms]

@app.get("/my/farms/{farm_id}")
def get_my_farm(
    farm_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Farmer access is required.",
        )

    with engine.connect() as connection:
        # First make sure this farm belongs to the logged-in farmer.
        farm = connection.execute(
            text("""
                SELECT
                    farm_id,
                    farm_name,
                    location,
                    total_area_acres
                FROM farms
                WHERE farm_id = :farm_id
                  AND farmer_id = :farmer_id
            """),
            {
                "farm_id": farm_id,
                "farmer_id": current_user["user_id"],
            },
        ).mappings().first()

        if not farm:
            raise HTTPException(
                status_code=404,
                detail="Farm not found.",
            )

        # Get plots belonging to this farm.
        plots = connection.execute(
            text("""
                SELECT
                    fp.plot_id,
                    fp.plot_name,
                    fp.area_acres,
                    fp.soil_type,
                    fp.irrigation_type,
                    fp.created_at
                FROM farm_plots fp
                WHERE fp.farm_id = :farm_id
                ORDER BY fp.plot_name
            """),
            {"farm_id": farm_id},
        ).mappings().all()

        # Get crops assigned to plots in this farm.
        crops = connection.execute(
            text("""
                SELECT
                    fc.farm_crop_id,
                    fc.farm_id,
                    fc.plot_id,
                    fc.crop_id,
                    c.crop_name,
                    c.scientific_name,
                    fc.season,
                    fc.planted_on,
                    fc.expected_harvest_on,
                    fc.status
                FROM farm_crops fc
                JOIN crops c
                    ON c.crop_id = fc.crop_id
                WHERE fc.farm_id = :farm_id
                ORDER BY fc.plot_id NULLS LAST,
                         fc.planted_on DESC NULLS LAST,
                         c.crop_name
            """),
            {"farm_id": farm_id},
        ).mappings().all()

    return {
        "farm": dict(farm),
        "plots": [dict(plot) for plot in plots],
        "crops": [dict(crop) for crop in crops],
    }


@app.post("/my/farms/{farm_id}/plots", status_code=status.HTTP_201_CREATED)
def create_farm_plot(
    farm_id: int,
    plot: FarmPlotCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Farmer access is required.",
        )

    if plot.farm_id != farm_id:
        raise HTTPException(
            status_code=400,
            detail="Farm ID does not match the requested farm.",
        )

    with engine.begin() as connection:
        # Make sure this farm belongs to the logged-in farmer.
        farm = connection.execute(
            text("""
                SELECT farm_id
                FROM farms
                WHERE farm_id = :farm_id
                  AND farmer_id = :farmer_id
            """),
            {
                "farm_id": farm_id,
                "farmer_id": current_user["user_id"],
            },
        ).first()

        if not farm:
            raise HTTPException(
                status_code=404,
                detail="Farm not found.",
            )

        new_plot = connection.execute(
            text("""
                INSERT INTO farm_plots (
                    farm_id,
                    plot_name,
                    area_acres,
                    soil_type,
                    irrigation_type
                )
                VALUES (
                    :farm_id,
                    :plot_name,
                    :area_acres,
                    :soil_type,
                    :irrigation_type
                )
                RETURNING
                    plot_id,
                    farm_id,
                    plot_name,
                    area_acres,
                    soil_type,
                    irrigation_type,
                    created_at
            """),
            {
                "farm_id": farm_id,
                "plot_name": plot.plot_name.strip(),
                "area_acres": plot.area_acres,
                "soil_type": plot.soil_type.strip()
                if plot.soil_type
                else None,
                "irrigation_type": plot.irrigation_type.strip()
                if plot.irrigation_type
                else None,
            },
        ).mappings().one()

    return dict(new_plot)

@app.post(
    "/my/farms/{farm_id}/crops",
    status_code=status.HTTP_201_CREATED,
)
def create_farm_crop(
    farm_id: int,
    crop: FarmCropCreate,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Farmer access is required.",
        )

    if crop.farm_id != farm_id:
        raise HTTPException(
            status_code=400,
            detail="Farm ID does not match the requested farm.",
        )

    if (
        crop.planted_on
        and crop.expected_harvest_on
        and crop.expected_harvest_on <= crop.planted_on
    ):
        raise HTTPException(
            status_code=400,
            detail="Expected harvest date must be after the planted date.",
        )

    with engine.begin() as connection:

        # 1. Verify that the farm belongs to the logged-in farmer.
        farm = connection.execute(
            text("""
                SELECT farm_id
                FROM farms
                WHERE farm_id = :farm_id
                  AND farmer_id = :farmer_id
            """),
            {
                "farm_id": farm_id,
                "farmer_id": current_user["user_id"],
            },
        ).first()

        if not farm:
            raise HTTPException(
                status_code=404,
                detail="Farm not found.",
            )

        # 2. Verify that the selected plot belongs to this farm.
        plot = connection.execute(
            text("""
                SELECT
                    plot_id,
                    farm_id,
                    plot_name
                FROM farm_plots
                WHERE plot_id = :plot_id
                  AND farm_id = :farm_id
            """),
            {
                "plot_id": crop.plot_id,
                "farm_id": farm_id,
            },
        ).first()

        if not plot:
            raise HTTPException(
                status_code=404,
                detail="Plot not found for this farm.",
            )

        # 3. Verify that the crop exists in the crop catalogue.
        crop_catalogue = connection.execute(
            text("""
                SELECT
                    crop_id,
                    crop_name,
                    scientific_name
                FROM crops
                WHERE crop_id = :crop_id
            """),
            {
                "crop_id": crop.crop_id,
            },
        ).mappings().first()

        if not crop_catalogue:
            raise HTTPException(
                status_code=404,
                detail="Crop not found in the crop catalogue.",
            )

        # 4. Create the farm crop.
        new_farm_crop = connection.execute(
            text("""
                INSERT INTO farm_crops (
                    farm_id,
                    plot_id,
                    crop_id,
                    season,
                    planted_on,
                    expected_harvest_on,
                    status
                )
                VALUES (
                    :farm_id,
                    :plot_id,
                    :crop_id,
                    :season,
                    :planted_on,
                    :expected_harvest_on,
                    'active'
                )
                RETURNING
                    farm_crop_id,
                    farm_id,
                    plot_id,
                    crop_id,
                    season,
                    planted_on,
                    expected_harvest_on,
                    status
            """),
            {
                "farm_id": farm_id,
                "plot_id": crop.plot_id,
                "crop_id": crop.crop_id,
                "season": crop.season.strip()
                if crop.season
                else None,
                "planted_on": crop.planted_on,
                "expected_harvest_on": crop.expected_harvest_on,
            },
        ).mappings().one()

    return {
        **dict(new_farm_crop),
        "crop_name": crop_catalogue["crop_name"],
        "scientific_name": crop_catalogue["scientific_name"],
        "plot_name": plot.plot_name,
    }

@app.get("/my/addresses")
def get_my_addresses(current_user: dict = Depends(get_current_user)):
    if not has_farmer_capability(current_user):
        raise HTTPException(status_code=403, detail="Farmer access is required.")

    with engine.connect() as connection:
        addresses = connection.execute(
            text("""
                SELECT
                    address_id, label, address_line1, village_or_city,
                    district, state, postal_code
                FROM addresses
                WHERE user_id = :user_id
                ORDER BY is_default DESC, address_id
            """),
            {"user_id": current_user["user_id"]},
        ).mappings().all()

    return [dict(address) for address in addresses]


@app.post("/my/bookings", status_code=status.HTTP_201_CREATED)
def create_my_booking(
    booking: CurrentUserBookingCreate,
    response: Response = None,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only farmers can create bookings.",
        )

    farmer_id = current_user["user_id"]

    # ---------------------------------------------------------
    # Basic time validation
    # ---------------------------------------------------------
    if booking.requested_end_at is None:
        raise HTTPException(
            status_code=400,
            detail="The booking end time is required.",
        )

    if booking.requested_end_at <= booking.requested_start_at:
        raise HTTPException(
            status_code=400,
            detail="The booking end time must be after the start time.",
        )

    duration = booking.requested_end_at - booking.requested_start_at

    # Bookings must be made in complete 1-hour units.
    if duration.total_seconds() % 3600 != 0:
        raise HTTPException(
            status_code=400,
            detail="Bookings must use complete 1-hour time slots.",
        )

    with engine.begin() as connection:
        from task_services import prepare_task_booking
        crop_link, replay = prepare_task_booking(connection, booking, farmer_id)
        if replay:
            if response is not None: response.status_code = 200
            return {"message": "Booking already created.", **replay}
        crop_link = crop_link or dict(crop_task_id=None, crop_context_snapshot=None, crop_request_key=None, crop_request_payload=None)

        # ---------------------------------------------------------
        # 1. Get service
        # ---------------------------------------------------------
        service = connection.execute(
            text("""
                SELECT
                    ss.supplier_service_id,
                    ss.supplier_id,
                    ss.service_name,
                    ss.pricing_unit,
                    ss.base_price,
                    sp.is_active AS provider_is_active,
                    sp.verified_at
                FROM supplier_services ss
                JOIN supplier_profiles sp
                    ON sp.supplier_id = ss.supplier_id
                WHERE ss.supplier_service_id = :service_id
                  AND ss.is_active = TRUE
            """),
            {
                "service_id": booking.supplier_service_id,
            },
        ).mappings().first()

        if not service:
            raise HTTPException(
                status_code=404,
                detail="Available service with a fixed price was not found.",
            )

        if (
            not service["provider_is_active"]
            or service["verified_at"] is None
        ):
            raise HTTPException(
                status_code=403,
                detail="This provider is not currently available for booking.",
            )

        if service["base_price"] is None:
            raise HTTPException(
                status_code=404,
                detail="Available service with a fixed price was not found.",
            )

        # ---------------------------------------------------------
        # 2. Validate farm ownership
        # ---------------------------------------------------------
        if booking.farm_id:
            owns_farm = connection.execute(
                text("""
                    SELECT farm_id
                    FROM farms
                    WHERE farm_id = :farm_id
                      AND farmer_id = :farmer_id
                """),
                {
                    "farm_id": booking.farm_id,
                    "farmer_id": farmer_id,
                },
            ).first()

            if not owns_farm:
                raise HTTPException(
                    status_code=403,
                    detail="You can only book services for your own farm.",
                )

        # ---------------------------------------------------------
        # 3. Validate address ownership
        # ---------------------------------------------------------
        if booking.service_address_id:
            owns_address = connection.execute(
                text("""
                    SELECT address_id
                    FROM addresses
                    WHERE address_id = :address_id
                      AND user_id = :user_id
                """),
                {
                    "address_id": booking.service_address_id,
                    "user_id": farmer_id,
                },
            ).first()

            if not owns_address:
                raise HTTPException(
                    status_code=403,
                    detail="You can only use your own service address.",
                )

        # ---------------------------------------------------------
        # 4. Generate every required hourly start time
        # ---------------------------------------------------------
        required_starts = []

        current_slot_start = booking.requested_start_at

        while current_slot_start < booking.requested_end_at:
            required_starts.append(current_slot_start)
            current_slot_start += timedelta(hours=1)

        if not required_starts:
            raise HTTPException(
                status_code=400,
                detail="At least one 1-hour booking slot is required.",
            )

        # ---------------------------------------------------------
        # 5. Find and lock ALL required availability slots
        # ---------------------------------------------------------
        availability_slots = connection.execute(
            text("""
                SELECT
                    a.availability_slot_id,
                    a.starts_at,
                    a.ends_at,
                    a.capacity
                FROM availability_slots a
                WHERE a.supplier_service_id = :supplier_service_id
                  AND a.status = 'available'
                  AND a.starts_at >= :requested_start_at
                  AND a.ends_at <= :requested_end_at
                ORDER BY a.starts_at
                FOR UPDATE
            """),
            {
                "supplier_service_id":
                    service["supplier_service_id"],
                "requested_start_at":
                    booking.requested_start_at,
                "requested_end_at":
                    booking.requested_end_at,
            },
        ).mappings().all()

        # ---------------------------------------------------------
        # 6. Verify that EVERY hourly slot exists
        # ---------------------------------------------------------
        slot_by_start = {
            slot["starts_at"]: slot
            for slot in availability_slots
        }

        missing_slots = [
            slot_start
            for slot_start in required_starts
            if slot_start not in slot_by_start
        ]

        if missing_slots:
            missing_text = ", ".join(
                str(slot) for slot in missing_slots
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "One or more requested hourly slots are not "
                    f"available: {missing_text}"
                ),
            )

        # ---------------------------------------------------------
        # 7. Check capacity for EVERY hourly slot
        # ---------------------------------------------------------
        quantity = Decimal(str(booking.quantity))

        for slot_start in required_starts:
            slot = slot_by_start[slot_start]

            reserved_quantity = connection.execute(
                text("""
                    SELECT COALESCE(SUM(r.reserved_quantity), 0)
                    FROM booking_slot_reservations r
                    JOIN bookings b
                        ON b.booking_id = r.booking_id
                    WHERE r.availability_slot_id =
                          :availability_slot_id
                      AND b.status NOT IN (
                          'cancelled',
                          'rejected'
                      )
                """),
                {
                    "availability_slot_id":
                        slot["availability_slot_id"],
                },
            ).scalar_one()

            if (
                Decimal(str(reserved_quantity))
                + quantity
                > Decimal(str(slot["capacity"]))
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"The time slot "
                        f"{slot['starts_at']} - {slot['ends_at']} "
                        "is no longer available for the requested "
                        "quantity."
                    ),
                )

        # ---------------------------------------------------------
        # 8. Calculate booking amount
        # ---------------------------------------------------------
        unit_price = Decimal(str(service["base_price"]))

        # Quantity remains the service quantity.
        # Duration is represented by the number of hourly
        # reservations rather than multiplying the service price.
        subtotal = unit_price * quantity

        booking_number = (
            f"AGR-{datetime.now():%Y%m%d%H%M%S%f}"
        )

        # ---------------------------------------------------------
        # 9. Create booking
        # ---------------------------------------------------------
        new_booking = connection.execute(
            text("""
                INSERT INTO bookings (
                    booking_number,
                    farmer_id,
                    supplier_id,
                    farm_id,
                    service_address_id,
                    requested_start_at,
                    requested_end_at,
                    status,
                    subtotal,
                    travel_fee,
                    platform_fee,
                    tax_amount,
                    discount_amount,
                    total_amount,
                    payment_status,
                    customer_notes,
                    crop_task_id,crop_context_snapshot,crop_request_key,crop_request_payload
                )
                VALUES (
                    :booking_number,
                    :farmer_id,
                    :supplier_id,
                    :farm_id,
                    :service_address_id,
                    :requested_start_at,
                    :requested_end_at,
                    'pending',
                    :subtotal,
                    0,
                    0,
                    0,
                    0,
                    :total_amount,
                    'unpaid',
                    :customer_notes,
                    :crop_task_id,CAST(:crop_context_snapshot AS jsonb),:crop_request_key,CAST(:crop_request_payload AS jsonb)
                )
                RETURNING
                    booking_id,
                    booking_number,
                    status,
                    total_amount,crop_task_id,crop_context_snapshot
            """),
            {
                **crop_link,
                "booking_number": booking_number,
                "farmer_id": farmer_id,
                "supplier_id": service["supplier_id"],
                "farm_id": booking.farm_id,
                "service_address_id": booking.service_address_id,
                "requested_start_at": booking.requested_start_at,
                "requested_end_at": booking.requested_end_at,
                "subtotal": subtotal,
                "total_amount": subtotal,
                "customer_notes": booking.customer_notes,
            },
        ).mappings().one()

        # ---------------------------------------------------------
        # 10. Create booking item
        # ---------------------------------------------------------
        connection.execute(
            text("""
                INSERT INTO booking_items (
                    booking_id,
                    supplier_service_id,
                    item_name,
                    quantity,
                    pricing_unit,
                    unit_price,
                    line_total,
                    scheduled_start_at,
                    scheduled_end_at
                )
                VALUES (
                    :booking_id,
                    :supplier_service_id,
                    :item_name,
                    :quantity,
                    :pricing_unit,
                    :unit_price,
                    :line_total,
                    :scheduled_start_at,
                    :scheduled_end_at
                )
            """),
            {
                "booking_id": new_booking["booking_id"],
                "supplier_service_id":
                    service["supplier_service_id"],
                "item_name": service["service_name"],
                "quantity": quantity,
                "pricing_unit": service["pricing_unit"],
                "unit_price": unit_price,
                "line_total": subtotal,
                "scheduled_start_at":
                    booking.requested_start_at,
                "scheduled_end_at":
                    booking.requested_end_at,
            },
        )

        # ---------------------------------------------------------
        # 11. Reserve EVERY hourly availability slot
        # ---------------------------------------------------------
        for slot_start in required_starts:
            slot = slot_by_start[slot_start]

            connection.execute(
                text("""
                    INSERT INTO booking_slot_reservations (
                        booking_id,
                        availability_slot_id,
                        reserved_quantity
                    )
                    VALUES (
                        :booking_id,
                        :availability_slot_id,
                        :reserved_quantity
                    )
                """),
                {
                    "booking_id": new_booking["booking_id"],
                    "availability_slot_id":
                        slot["availability_slot_id"],
                    "reserved_quantity": quantity,
                },
            )

        # ---------------------------------------------------------
        # 12. Record booking history
        # ---------------------------------------------------------
        connection.execute(
            text("""
                INSERT INTO booking_status_history (
                    booking_id,
                    old_status,
                    new_status,
                    changed_by,
                    notes
                )
                VALUES (
                    :booking_id,
                    NULL,
                    'pending',
                    :farmer_id,
                    'Booking created.'
                )
            """),
            {
                "booking_id": new_booking["booking_id"],
                "farmer_id": farmer_id,
            },
        )

        # ---------------------------------------------------------
        # 13. Notify supplier
        # ---------------------------------------------------------
        create_notification(
            connection=connection,
            user_id=service["supplier_id"],
            title="New booking received",
            message=(
                f"New booking {new_booking['booking_number']} "
                f"for {service['service_name']} has been received."
            ),
            notification_type="booking",
            related_booking_id=new_booking["booking_id"],
        )

    return {
        "message": "Booking created successfully.",
        **dict(new_booking),
    }


@app.post("/my/bookings/{booking_id}/cancel")
def cancel_my_booking(
    booking_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not has_farmer_capability(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only farmers can cancel bookings.",
        )

    farmer_id = current_user["user_id"]

    with engine.begin() as connection:
        booking = connection.execute(
            text("""
                SELECT
                    b.booking_id,
                    b.booking_number,
                    b.farmer_id,
                    b.supplier_id,
                    b.status,
                    b.payment_status,
                    COALESCE(sp.business_name, u.full_name) AS supplier_name
                FROM bookings b
                JOIN supplier_profiles sp
                    ON sp.supplier_id = b.supplier_id
                JOIN users u
                    ON u.user_id = sp.supplier_id
                WHERE b.booking_id = :booking_id
                  AND b.farmer_id = :farmer_id
                FOR UPDATE
            """),
            {
                "booking_id": booking_id,
                "farmer_id": farmer_id,
            },
        ).mappings().first()

        if not booking:
            raise HTTPException(
                status_code=404,
                detail="Booking not found.",
            )

        if booking["status"] not in (
            "pending",
            "quoted",
            "confirmed",
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Booking cannot be cancelled when its status is "
                    f"'{booking['status']}'."
                ),
            )

        if booking["payment_status"] == "paid":
            raise HTTPException(
                status_code=400,
                detail=(
                    "This booking has already been paid. "
                    "Payment refund must be processed before cancellation."
                ),
            )

        old_status = booking["status"]

        connection.execute(
            text("""
                UPDATE bookings
                SET status = 'cancelled',
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = :booking_id
            """),
            {
                "booking_id": booking_id,
            },
        )

        connection.execute(
            text("""
                INSERT INTO booking_status_history (
                    booking_id,
                    old_status,
                    new_status,
                    changed_by,
                    notes
                )
                VALUES (
                    :booking_id,
                    :old_status,
                    'cancelled',
                    :farmer_id,
                    'Booking cancelled by farmer.'
                )
            """),
            {
                "booking_id": booking_id,
                "old_status": old_status,
                "farmer_id": farmer_id,
            },
        )

        create_notification(
            connection=connection,
            user_id=booking["supplier_id"],
            title="Booking cancelled",
            message=(
                f"Booking {booking['booking_number']} has been "
                f"cancelled by the farmer."
            ),
            notification_type="booking",
            related_booking_id=booking["booking_id"],
        )

    return {
        "message": "Booking cancelled successfully.",
        "booking_id": booking_id,
        "booking_number": booking["booking_number"],
        "status": "cancelled",
    }
@app.get("/farmers/{farmer_id}/bookings")
def get_farmer_bookings(
    farmer_id: int,
    current_user: dict = Depends(get_current_user),
):
    if (
        not has_farmer_capability(current_user)
        or current_user["user_id"] != farmer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own bookings.",
        )

    with engine.connect() as connection:
        bookings = connection.execute(
            text("""
                SELECT
                    b.booking_id,
                    b.booking_number,
                    b.crop_task_id,b.crop_context_snapshot,
                    b.status,
                    b.requested_start_at,
                    b.requested_end_at,
                    b.total_amount,
                    b.payment_status,
                    sp.business_name AS supplier_name,
                    STRING_AGG(
                        bi.item_name,
                        ', '
                        ORDER BY bi.item_name
                    ) AS service_names,

                    -- Required for rescheduling
                    MIN(bi.supplier_service_id) AS supplier_service_id

                FROM bookings b

                JOIN supplier_profiles sp
                    ON sp.supplier_id = b.supplier_id

                LEFT JOIN booking_items bi
                    ON bi.booking_id = b.booking_id

                WHERE b.farmer_id = :farmer_id

                GROUP BY
                    b.booking_id,
                    b.booking_number,
                    b.status,
                    b.requested_start_at,
                    b.requested_end_at,
                    b.total_amount,
                    b.payment_status,
                    sp.business_name

                ORDER BY b.created_at DESC
            """),
            {
                "farmer_id": farmer_id,
            },
        ).mappings().all()

    return [
        dict(booking)
        for booking in bookings
    ]

# Crop Management is an additive router; existing marketplace routes are preserved.
from crop_management import create_router as create_crop_management_router
app.include_router(create_crop_management_router(engine, get_current_user, get_effective_capabilities))

from field_work import create_field_router
app.include_router(create_field_router(engine, get_current_user, get_effective_capabilities))

from farm_ledger import create_ledger_router
app.include_router(create_ledger_router(engine, get_current_user, get_effective_capabilities))

from farm_inputs import create_catalogue_router
app.include_router(create_catalogue_router(engine, get_current_user, get_effective_capabilities))

from harvest_management import create_harvest_router
app.include_router(create_harvest_router(engine, get_current_user, get_effective_capabilities))

from production_lifecycle import create_lifecycle_router
app.include_router(create_lifecycle_router(engine, get_current_user, get_effective_capabilities))

from task_services import create_task_service_router
app.include_router(create_task_service_router(engine, get_current_user, get_effective_capabilities))

from officer_applications import create_application_router
app.include_router(create_application_router(engine, get_current_user, get_effective_capabilities))
