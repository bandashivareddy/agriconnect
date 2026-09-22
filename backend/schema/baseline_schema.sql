--
-- PostgreSQL database dump
--

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.addresses (
    address_id integer NOT NULL,
    user_id integer NOT NULL,
    label character varying(50) DEFAULT 'Primary'::character varying,
    address_line1 character varying(200) NOT NULL,
    address_line2 character varying(200),
    village_or_city character varying(100) NOT NULL,
    district character varying(100),
    state character varying(100) NOT NULL,
    postal_code character varying(20),
    latitude numeric(10,7),
    longitude numeric(10,7),
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: addresses_address_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.addresses_address_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: addresses_address_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.addresses_address_id_seq OWNED BY public.addresses.address_id;


--
-- Name: availability_slots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_slots (
    availability_slot_id integer NOT NULL,
    supplier_service_id integer,
    equipment_id integer,
    starts_at timestamp without time zone NOT NULL,
    ends_at timestamp without time zone NOT NULL,
    capacity integer DEFAULT 1 NOT NULL,
    status character varying(20) DEFAULT 'available'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT availability_slots_capacity_check CHECK ((capacity > 0)),
    CONSTRAINT availability_slots_check CHECK ((ends_at > starts_at)),
    CONSTRAINT availability_slots_check1 CHECK ((((supplier_service_id IS NOT NULL) AND (equipment_id IS NULL)) OR ((supplier_service_id IS NULL) AND (equipment_id IS NOT NULL)))),
    CONSTRAINT availability_slots_status_check CHECK (((status)::text = ANY ((ARRAY['available'::character varying, 'blocked'::character varying, 'unavailable'::character varying])::text[])))
);


--
-- Name: availability_slots_availability_slot_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_slots_availability_slot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_slots_availability_slot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_slots_availability_slot_id_seq OWNED BY public.availability_slots.availability_slot_id;


--
-- Name: booking_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_items (
    booking_item_id integer NOT NULL,
    booking_id integer NOT NULL,
    supplier_service_id integer,
    equipment_id integer,
    item_name character varying(150) NOT NULL,
    quantity numeric(10,2) DEFAULT 1 NOT NULL,
    pricing_unit character varying(20) NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    line_total numeric(12,2) NOT NULL,
    scheduled_start_at timestamp without time zone,
    scheduled_end_at timestamp without time zone,
    CONSTRAINT booking_items_check CHECK ((((supplier_service_id IS NOT NULL) AND (equipment_id IS NULL)) OR ((supplier_service_id IS NULL) AND (equipment_id IS NOT NULL)))),
    CONSTRAINT booking_items_line_total_check CHECK ((line_total >= (0)::numeric)),
    CONSTRAINT booking_items_quantity_check CHECK ((quantity > (0)::numeric)),
    CONSTRAINT booking_items_unit_price_check CHECK ((unit_price >= (0)::numeric))
);


--
-- Name: booking_items_booking_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.booking_items_booking_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_items_booking_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.booking_items_booking_item_id_seq OWNED BY public.booking_items.booking_item_id;


--
-- Name: booking_slot_reservations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_slot_reservations (
    reservation_id integer NOT NULL,
    booking_id integer NOT NULL,
    availability_slot_id integer NOT NULL,
    reserved_quantity integer DEFAULT 1 NOT NULL,
    CONSTRAINT booking_slot_reservations_reserved_quantity_check CHECK ((reserved_quantity > 0))
);


--
-- Name: booking_slot_reservations_reservation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.booking_slot_reservations_reservation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_slot_reservations_reservation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.booking_slot_reservations_reservation_id_seq OWNED BY public.booking_slot_reservations.reservation_id;


--
-- Name: booking_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_status_history (
    history_id integer NOT NULL,
    booking_id integer NOT NULL,
    old_status character varying(30),
    new_status character varying(30) NOT NULL,
    changed_by integer,
    notes text,
    changed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: booking_status_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.booking_status_history_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_status_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.booking_status_history_history_id_seq OWNED BY public.booking_status_history.history_id;


--
-- Name: bookings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bookings (
    booking_id integer NOT NULL,
    booking_number character varying(30) NOT NULL,
    farmer_id integer NOT NULL,
    supplier_id integer NOT NULL,
    farm_id integer,
    service_address_id integer,
    requested_start_at timestamp without time zone NOT NULL,
    requested_end_at timestamp without time zone,
    status character varying(30) DEFAULT 'pending'::character varying NOT NULL,
    subtotal numeric(12,2) DEFAULT 0 NOT NULL,
    travel_fee numeric(12,2) DEFAULT 0 NOT NULL,
    platform_fee numeric(12,2) DEFAULT 0 NOT NULL,
    tax_amount numeric(12,2) DEFAULT 0 NOT NULL,
    discount_amount numeric(12,2) DEFAULT 0 NOT NULL,
    total_amount numeric(12,2) DEFAULT 0 NOT NULL,
    payment_status character varying(20) DEFAULT 'unpaid'::character varying NOT NULL,
    customer_notes text,
    cancellation_reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT bookings_check CHECK (((requested_end_at IS NULL) OR (requested_end_at > requested_start_at))),
    CONSTRAINT bookings_check1 CHECK (((subtotal >= (0)::numeric) AND (travel_fee >= (0)::numeric) AND (platform_fee >= (0)::numeric) AND (tax_amount >= (0)::numeric) AND (discount_amount >= (0)::numeric) AND (total_amount >= (0)::numeric))),
    CONSTRAINT bookings_payment_status_check CHECK (((payment_status)::text = ANY ((ARRAY['unpaid'::character varying, 'partial'::character varying, 'paid'::character varying, 'refunded'::character varying, 'failed'::character varying])::text[]))),
    CONSTRAINT bookings_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'quoted'::character varying, 'confirmed'::character varying, 'in_progress'::character varying, 'completed'::character varying, 'cancelled'::character varying, 'rejected'::character varying, 'disputed'::character varying])::text[])))
);


--
-- Name: bookings_booking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bookings_booking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bookings_booking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bookings_booking_id_seq OWNED BY public.bookings.booking_id;


--
-- Name: crops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crops (
    crop_id integer NOT NULL,
    crop_name character varying(100) NOT NULL,
    scientific_name character varying(150)
);


--
-- Name: crops_crop_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crops_crop_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crops_crop_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crops_crop_id_seq OWNED BY public.crops.crop_id;


--
-- Name: disputes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disputes (
    dispute_id integer NOT NULL,
    booking_id integer NOT NULL,
    opened_by integer NOT NULL,
    reason character varying(150) NOT NULL,
    description text NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    resolution text,
    resolved_by integer,
    resolved_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT disputes_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'under_review'::character varying, 'resolved'::character varying, 'closed'::character varying])::text[])))
);


--
-- Name: disputes_dispute_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disputes_dispute_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: disputes_dispute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disputes_dispute_id_seq OWNED BY public.disputes.dispute_id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    document_id integer NOT NULL,
    user_id integer NOT NULL,
    booking_id integer,
    document_type character varying(50) NOT NULL,
    file_name character varying(255) NOT NULL,
    file_url text NOT NULL,
    verification_status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT documents_verification_status_check CHECK (((verification_status)::text = ANY ((ARRAY['pending'::character varying, 'verified'::character varying, 'rejected'::character varying])::text[])))
);


--
-- Name: documents_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documents_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documents_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documents_document_id_seq OWNED BY public.documents.document_id;


--
-- Name: equipment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipment (
    equipment_id integer NOT NULL,
    supplier_id integer NOT NULL,
    equipment_category_id integer,
    equipment_name character varying(150) NOT NULL,
    brand character varying(100),
    model character varying(100),
    description text,
    daily_rate numeric(12,2),
    security_deposit numeric(12,2) DEFAULT 0 NOT NULL,
    quantity_available integer DEFAULT 1 NOT NULL,
    equipment_details jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT equipment_daily_rate_check CHECK (((daily_rate IS NULL) OR (daily_rate >= (0)::numeric))),
    CONSTRAINT equipment_quantity_available_check CHECK ((quantity_available >= 0)),
    CONSTRAINT equipment_security_deposit_check CHECK ((security_deposit >= (0)::numeric))
);


--
-- Name: equipment_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipment_categories (
    equipment_category_id integer NOT NULL,
    category_name character varying(100) NOT NULL,
    description text
);


--
-- Name: equipment_categories_equipment_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipment_categories_equipment_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_categories_equipment_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipment_categories_equipment_category_id_seq OWNED BY public.equipment_categories.equipment_category_id;


--
-- Name: equipment_equipment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipment_equipment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipment_equipment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipment_equipment_id_seq OWNED BY public.equipment.equipment_id;


--
-- Name: farm_crops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.farm_crops (
    farm_crop_id integer NOT NULL,
    farm_id integer NOT NULL,
    plot_id integer,
    crop_id integer NOT NULL,
    season character varying(50),
    planted_on date,
    expected_harvest_on date,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    CONSTRAINT farm_crops_status_check CHECK (((status)::text = ANY ((ARRAY['planned'::character varying, 'active'::character varying, 'harvested'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: farm_crops_farm_crop_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.farm_crops_farm_crop_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: farm_crops_farm_crop_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.farm_crops_farm_crop_id_seq OWNED BY public.farm_crops.farm_crop_id;


--
-- Name: farm_plots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.farm_plots (
    plot_id integer NOT NULL,
    farm_id integer NOT NULL,
    plot_name character varying(120) NOT NULL,
    area_acres numeric(10,2),
    soil_type character varying(100),
    irrigation_type character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: farm_plots_plot_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.farm_plots_plot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: farm_plots_plot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.farm_plots_plot_id_seq OWNED BY public.farm_plots.plot_id;


--
-- Name: farms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.farms (
    farm_id integer NOT NULL,
    farmer_id integer NOT NULL,
    farm_name character varying(150) NOT NULL,
    location character varying(255) NOT NULL,
    total_area_acres numeric(10,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: farms_farm_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.farms_farm_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: farms_farm_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.farms_farm_id_seq OWNED BY public.farms.farm_id;


--
-- Name: favourites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.favourites (
    favourite_id integer NOT NULL,
    farmer_id integer NOT NULL,
    supplier_id integer,
    supplier_service_id integer,
    equipment_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT favourites_check CHECK ((((((supplier_id IS NOT NULL))::integer + ((supplier_service_id IS NOT NULL))::integer) + ((equipment_id IS NOT NULL))::integer) = 1))
);


--
-- Name: favourites_favourite_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.favourites_favourite_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: favourites_favourite_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.favourites_favourite_id_seq OWNED BY public.favourites.favourite_id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    notification_id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(150) NOT NULL,
    message text NOT NULL,
    notification_type character varying(50),
    related_booking_id integer,
    is_read boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: notifications_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_notification_id_seq OWNED BY public.notifications.notification_id;


--
-- Name: payment_refunds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_refunds (
    refund_id integer NOT NULL,
    payment_id integer NOT NULL,
    amount numeric(12,2) NOT NULL,
    reason text,
    provider_refund_id character varying(150),
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    processed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT payment_refunds_amount_check CHECK ((amount > (0)::numeric)),
    CONSTRAINT payment_refunds_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'processed'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: payment_refunds_refund_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_refunds_refund_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_refunds_refund_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_refunds_refund_id_seq OWNED BY public.payment_refunds.refund_id;


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    payment_id integer NOT NULL,
    booking_id integer NOT NULL,
    payer_id integer NOT NULL,
    amount numeric(12,2) NOT NULL,
    currency character(3) DEFAULT 'INR'::bpchar NOT NULL,
    payment_method character varying(30) NOT NULL,
    provider character varying(80),
    provider_transaction_id character varying(150),
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    paid_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT payments_amount_check CHECK ((amount > (0)::numeric)),
    CONSTRAINT payments_payment_method_check CHECK (((payment_method)::text = ANY ((ARRAY['upi'::character varying, 'card'::character varying, 'net_banking'::character varying, 'cash'::character varying, 'wallet'::character varying, 'bank_transfer'::character varying])::text[]))),
    CONSTRAINT payments_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'authorized'::character varying, 'paid'::character varying, 'failed'::character varying, 'refunded'::character varying])::text[])))
);


--
-- Name: payments_payment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payments_payment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payments_payment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payments_payment_id_seq OWNED BY public.payments.payment_id;


--
-- Name: reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reviews (
    review_id integer NOT NULL,
    booking_id integer NOT NULL,
    reviewer_id integer NOT NULL,
    supplier_id integer NOT NULL,
    rating integer NOT NULL,
    review_text text,
    supplier_response text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT reviews_rating_check CHECK (((rating >= 1) AND (rating <= 5)))
);


--
-- Name: reviews_review_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reviews_review_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reviews_review_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reviews_review_id_seq OWNED BY public.reviews.review_id;


--
-- Name: service_areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_areas (
    service_area_id integer NOT NULL,
    supplier_id integer NOT NULL,
    district character varying(100) NOT NULL,
    state character varying(100) NOT NULL,
    postal_code character varying(20),
    travel_fee numeric(12,2) DEFAULT 0 NOT NULL,
    CONSTRAINT service_areas_travel_fee_check CHECK ((travel_fee >= (0)::numeric))
);


--
-- Name: service_areas_service_area_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_areas_service_area_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_areas_service_area_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_areas_service_area_id_seq OWNED BY public.service_areas.service_area_id;


--
-- Name: service_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_categories (
    category_id integer NOT NULL,
    parent_category_id integer,
    category_name character varying(100) NOT NULL,
    description text,
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: service_categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.service_categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: service_categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.service_categories_category_id_seq OWNED BY public.service_categories.category_id;


--
-- Name: service_equipment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_equipment (
    supplier_service_id integer NOT NULL,
    equipment_id integer NOT NULL
);


--
-- Name: supplier_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_profiles (
    supplier_id integer NOT NULL,
    business_name character varying(150) NOT NULL,
    description text,
    business_registration_no character varying(100),
    gstin character varying(30),
    verified_at timestamp without time zone,
    average_rating numeric(3,2) DEFAULT 0 NOT NULL,
    total_reviews integer DEFAULT 0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT supplier_profiles_average_rating_check CHECK (((average_rating >= (0)::numeric) AND (average_rating <= (5)::numeric)))
);


--
-- Name: supplier_services; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supplier_services (
    supplier_service_id integer NOT NULL,
    supplier_id integer NOT NULL,
    category_id integer NOT NULL,
    service_name character varying(150) NOT NULL,
    description text,
    pricing_unit character varying(20) NOT NULL,
    base_price numeric(12,2),
    minimum_charge numeric(12,2),
    estimated_duration_minutes integer,
    service_details jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT supplier_services_base_price_check CHECK (((base_price IS NULL) OR (base_price >= (0)::numeric))),
    CONSTRAINT supplier_services_minimum_charge_check CHECK (((minimum_charge IS NULL) OR (minimum_charge >= (0)::numeric))),
    CONSTRAINT supplier_services_pricing_unit_check CHECK (((pricing_unit)::text = ANY ((ARRAY['fixed'::character varying, 'hour'::character varying, 'day'::character varying, 'acre'::character varying, 'trip'::character varying, 'custom'::character varying])::text[])))
);


--
-- Name: supplier_services_supplier_service_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.supplier_services_supplier_service_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: supplier_services_supplier_service_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.supplier_services_supplier_service_id_seq OWNED BY public.supplier_services.supplier_service_id;


--
-- Name: user_capabilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_capabilities (
    user_id integer NOT NULL,
    capability character varying(30) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT user_capabilities_capability_check CHECK (((capability)::text = ANY ((ARRAY['farmer'::character varying, 'provider'::character varying, 'admin'::character varying])::text[])))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    full_name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    phone character varying(20),
    password_hash text NOT NULL,
    user_role character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT users_user_role_check CHECK (((user_role)::text = ANY ((ARRAY['farmer'::character varying, 'supplier'::character varying, 'admin'::character varying])::text[])))
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: addresses address_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses ALTER COLUMN address_id SET DEFAULT nextval('public.addresses_address_id_seq'::regclass);


--
-- Name: availability_slots availability_slot_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_slots ALTER COLUMN availability_slot_id SET DEFAULT nextval('public.availability_slots_availability_slot_id_seq'::regclass);


--
-- Name: booking_items booking_item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_items ALTER COLUMN booking_item_id SET DEFAULT nextval('public.booking_items_booking_item_id_seq'::regclass);


--
-- Name: booking_slot_reservations reservation_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_slot_reservations ALTER COLUMN reservation_id SET DEFAULT nextval('public.booking_slot_reservations_reservation_id_seq'::regclass);


--
-- Name: booking_status_history history_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_status_history ALTER COLUMN history_id SET DEFAULT nextval('public.booking_status_history_history_id_seq'::regclass);


--
-- Name: bookings booking_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings ALTER COLUMN booking_id SET DEFAULT nextval('public.bookings_booking_id_seq'::regclass);


--
-- Name: crops crop_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crops ALTER COLUMN crop_id SET DEFAULT nextval('public.crops_crop_id_seq'::regclass);


--
-- Name: disputes dispute_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes ALTER COLUMN dispute_id SET DEFAULT nextval('public.disputes_dispute_id_seq'::regclass);


--
-- Name: documents document_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents ALTER COLUMN document_id SET DEFAULT nextval('public.documents_document_id_seq'::regclass);


--
-- Name: equipment equipment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment ALTER COLUMN equipment_id SET DEFAULT nextval('public.equipment_equipment_id_seq'::regclass);


--
-- Name: equipment_categories equipment_category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_categories ALTER COLUMN equipment_category_id SET DEFAULT nextval('public.equipment_categories_equipment_category_id_seq'::regclass);


--
-- Name: farm_crops farm_crop_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_crops ALTER COLUMN farm_crop_id SET DEFAULT nextval('public.farm_crops_farm_crop_id_seq'::regclass);


--
-- Name: farm_plots plot_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_plots ALTER COLUMN plot_id SET DEFAULT nextval('public.farm_plots_plot_id_seq'::regclass);


--
-- Name: farms farm_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farms ALTER COLUMN farm_id SET DEFAULT nextval('public.farms_farm_id_seq'::regclass);


--
-- Name: favourites favourite_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favourites ALTER COLUMN favourite_id SET DEFAULT nextval('public.favourites_favourite_id_seq'::regclass);


--
-- Name: notifications notification_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN notification_id SET DEFAULT nextval('public.notifications_notification_id_seq'::regclass);


--
-- Name: payment_refunds refund_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_refunds ALTER COLUMN refund_id SET DEFAULT nextval('public.payment_refunds_refund_id_seq'::regclass);


--
-- Name: payments payment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments ALTER COLUMN payment_id SET DEFAULT nextval('public.payments_payment_id_seq'::regclass);


--
-- Name: reviews review_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews ALTER COLUMN review_id SET DEFAULT nextval('public.reviews_review_id_seq'::regclass);


--
-- Name: service_areas service_area_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_areas ALTER COLUMN service_area_id SET DEFAULT nextval('public.service_areas_service_area_id_seq'::regclass);


--
-- Name: service_categories category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories ALTER COLUMN category_id SET DEFAULT nextval('public.service_categories_category_id_seq'::regclass);


--
-- Name: supplier_services supplier_service_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_services ALTER COLUMN supplier_service_id SET DEFAULT nextval('public.supplier_services_supplier_service_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: addresses addresses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_pkey PRIMARY KEY (address_id);


--
-- Name: availability_slots availability_slots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_slots
    ADD CONSTRAINT availability_slots_pkey PRIMARY KEY (availability_slot_id);


--
-- Name: booking_items booking_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_items
    ADD CONSTRAINT booking_items_pkey PRIMARY KEY (booking_item_id);


--
-- Name: booking_slot_reservations booking_slot_reservations_booking_id_availability_slot_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_slot_reservations
    ADD CONSTRAINT booking_slot_reservations_booking_id_availability_slot_id_key UNIQUE (booking_id, availability_slot_id);


--
-- Name: booking_slot_reservations booking_slot_reservations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_slot_reservations
    ADD CONSTRAINT booking_slot_reservations_pkey PRIMARY KEY (reservation_id);


--
-- Name: booking_status_history booking_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_status_history
    ADD CONSTRAINT booking_status_history_pkey PRIMARY KEY (history_id);


--
-- Name: bookings bookings_booking_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_booking_number_key UNIQUE (booking_number);


--
-- Name: bookings bookings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_pkey PRIMARY KEY (booking_id);


--
-- Name: crops crops_crop_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crops
    ADD CONSTRAINT crops_crop_name_key UNIQUE (crop_name);


--
-- Name: crops crops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crops
    ADD CONSTRAINT crops_pkey PRIMARY KEY (crop_id);


--
-- Name: disputes disputes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_pkey PRIMARY KEY (dispute_id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (document_id);


--
-- Name: equipment_categories equipment_categories_category_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_categories
    ADD CONSTRAINT equipment_categories_category_name_key UNIQUE (category_name);


--
-- Name: equipment_categories equipment_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment_categories
    ADD CONSTRAINT equipment_categories_pkey PRIMARY KEY (equipment_category_id);


--
-- Name: equipment equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_pkey PRIMARY KEY (equipment_id);


--
-- Name: farm_crops farm_crops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_crops
    ADD CONSTRAINT farm_crops_pkey PRIMARY KEY (farm_crop_id);


--
-- Name: farm_plots farm_plots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_plots
    ADD CONSTRAINT farm_plots_pkey PRIMARY KEY (plot_id);


--
-- Name: farms farms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farms
    ADD CONSTRAINT farms_pkey PRIMARY KEY (farm_id);


--
-- Name: favourites favourites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favourites
    ADD CONSTRAINT favourites_pkey PRIMARY KEY (favourite_id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (notification_id);


--
-- Name: payment_refunds payment_refunds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_refunds
    ADD CONSTRAINT payment_refunds_pkey PRIMARY KEY (refund_id);


--
-- Name: payment_refunds payment_refunds_provider_refund_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_refunds
    ADD CONSTRAINT payment_refunds_provider_refund_id_key UNIQUE (provider_refund_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (payment_id);


--
-- Name: payments payments_provider_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_provider_transaction_id_key UNIQUE (provider_transaction_id);


--
-- Name: reviews reviews_booking_id_reviewer_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_booking_id_reviewer_id_key UNIQUE (booking_id, reviewer_id);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (review_id);


--
-- Name: service_areas service_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_areas
    ADD CONSTRAINT service_areas_pkey PRIMARY KEY (service_area_id);


--
-- Name: service_areas service_areas_supplier_id_district_state_postal_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_areas
    ADD CONSTRAINT service_areas_supplier_id_district_state_postal_code_key UNIQUE (supplier_id, district, state, postal_code);


--
-- Name: service_categories service_categories_category_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_category_name_key UNIQUE (category_name);


--
-- Name: service_categories service_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_pkey PRIMARY KEY (category_id);


--
-- Name: service_equipment service_equipment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_equipment
    ADD CONSTRAINT service_equipment_pkey PRIMARY KEY (supplier_service_id, equipment_id);


--
-- Name: supplier_profiles supplier_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_profiles
    ADD CONSTRAINT supplier_profiles_pkey PRIMARY KEY (supplier_id);


--
-- Name: supplier_services supplier_services_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_services
    ADD CONSTRAINT supplier_services_pkey PRIMARY KEY (supplier_service_id);


--
-- Name: user_capabilities user_capabilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_capabilities
    ADD CONSTRAINT user_capabilities_pkey PRIMARY KEY (user_id, capability);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: idx_bookings_farmer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookings_farmer ON public.bookings USING btree (farmer_id);


--
-- Name: idx_bookings_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookings_status ON public.bookings USING btree (status);


--
-- Name: idx_bookings_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookings_supplier ON public.bookings USING btree (supplier_id);


--
-- Name: idx_equipment_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_equipment_supplier ON public.equipment USING btree (supplier_id);


--
-- Name: idx_farms_farmer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_farms_farmer ON public.farms USING btree (farmer_id);


--
-- Name: idx_notifications_user_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_read ON public.notifications USING btree (user_id, is_read);


--
-- Name: idx_payments_booking; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_booking ON public.payments USING btree (booking_id);


--
-- Name: idx_supplier_services_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_services_category ON public.supplier_services USING btree (category_id);


--
-- Name: idx_supplier_services_supplier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_supplier_services_supplier ON public.supplier_services USING btree (supplier_id);


--
-- Name: addresses addresses_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- Name: availability_slots availability_slots_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_slots
    ADD CONSTRAINT availability_slots_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(equipment_id) ON DELETE CASCADE;


--
-- Name: availability_slots availability_slots_supplier_service_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_slots
    ADD CONSTRAINT availability_slots_supplier_service_id_fkey FOREIGN KEY (supplier_service_id) REFERENCES public.supplier_services(supplier_service_id) ON DELETE CASCADE;


--
-- Name: booking_items booking_items_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_items
    ADD CONSTRAINT booking_items_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: booking_items booking_items_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_items
    ADD CONSTRAINT booking_items_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(equipment_id);


--
-- Name: booking_items booking_items_supplier_service_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_items
    ADD CONSTRAINT booking_items_supplier_service_id_fkey FOREIGN KEY (supplier_service_id) REFERENCES public.supplier_services(supplier_service_id);


--
-- Name: booking_slot_reservations booking_slot_reservations_availability_slot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_slot_reservations
    ADD CONSTRAINT booking_slot_reservations_availability_slot_id_fkey FOREIGN KEY (availability_slot_id) REFERENCES public.availability_slots(availability_slot_id);


--
-- Name: booking_slot_reservations booking_slot_reservations_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_slot_reservations
    ADD CONSTRAINT booking_slot_reservations_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: booking_status_history booking_status_history_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_status_history
    ADD CONSTRAINT booking_status_history_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: booking_status_history booking_status_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_status_history
    ADD CONSTRAINT booking_status_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public.users(user_id) ON DELETE SET NULL;


--
-- Name: bookings bookings_farm_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_farm_id_fkey FOREIGN KEY (farm_id) REFERENCES public.farms(farm_id) ON DELETE SET NULL;


--
-- Name: bookings bookings_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(user_id);


--
-- Name: bookings bookings_service_address_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_service_address_id_fkey FOREIGN KEY (service_address_id) REFERENCES public.addresses(address_id) ON DELETE SET NULL;


--
-- Name: bookings bookings_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier_profiles(supplier_id);


--
-- Name: disputes disputes_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: disputes disputes_opened_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_opened_by_fkey FOREIGN KEY (opened_by) REFERENCES public.users(user_id);


--
-- Name: disputes disputes_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(user_id) ON DELETE SET NULL;


--
-- Name: documents documents_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: documents documents_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- Name: equipment equipment_equipment_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_equipment_category_id_fkey FOREIGN KEY (equipment_category_id) REFERENCES public.equipment_categories(equipment_category_id) ON DELETE SET NULL;


--
-- Name: equipment equipment_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipment
    ADD CONSTRAINT equipment_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier_profiles(supplier_id) ON DELETE CASCADE;


--
-- Name: farm_crops farm_crops_crop_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_crops
    ADD CONSTRAINT farm_crops_crop_id_fkey FOREIGN KEY (crop_id) REFERENCES public.crops(crop_id);


--
-- Name: farm_crops farm_crops_farm_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_crops
    ADD CONSTRAINT farm_crops_farm_id_fkey FOREIGN KEY (farm_id) REFERENCES public.farms(farm_id) ON DELETE CASCADE;


--
-- Name: farm_crops farm_crops_plot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_crops
    ADD CONSTRAINT farm_crops_plot_id_fkey FOREIGN KEY (plot_id) REFERENCES public.farm_plots(plot_id) ON DELETE SET NULL;


--
-- Name: farm_plots farm_plots_farm_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farm_plots
    ADD CONSTRAINT farm_plots_farm_id_fkey FOREIGN KEY (farm_id) REFERENCES public.farms(farm_id) ON DELETE CASCADE;


--
-- Name: farms farms_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.farms
    ADD CONSTRAINT farms_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- Name: favourites favourites_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favourites
    ADD CONSTRAINT favourites_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(equipment_id) ON DELETE CASCADE;


--
-- Name: favourites favourites_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favourites
    ADD CONSTRAINT favourites_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- Name: favourites favourites_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favourites
    ADD CONSTRAINT favourites_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier_profiles(supplier_id) ON DELETE CASCADE;


--
-- Name: favourites favourites_supplier_service_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.favourites
    ADD CONSTRAINT favourites_supplier_service_id_fkey FOREIGN KEY (supplier_service_id) REFERENCES public.supplier_services(supplier_service_id) ON DELETE CASCADE;


--
-- Name: notifications notifications_related_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_related_booking_id_fkey FOREIGN KEY (related_booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- Name: payment_refunds payment_refunds_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_refunds
    ADD CONSTRAINT payment_refunds_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(payment_id) ON DELETE CASCADE;


--
-- Name: payments payments_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: payments payments_payer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_payer_id_fkey FOREIGN KEY (payer_id) REFERENCES public.users(user_id);


--
-- Name: reviews reviews_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(booking_id) ON DELETE CASCADE;


--
-- Name: reviews reviews_reviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(user_id);


--
-- Name: reviews reviews_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier_profiles(supplier_id);


--
-- Name: service_areas service_areas_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_areas
    ADD CONSTRAINT service_areas_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier_profiles(supplier_id) ON DELETE CASCADE;


--
-- Name: service_categories service_categories_parent_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_categories
    ADD CONSTRAINT service_categories_parent_category_id_fkey FOREIGN KEY (parent_category_id) REFERENCES public.service_categories(category_id) ON DELETE SET NULL;


--
-- Name: service_equipment service_equipment_equipment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_equipment
    ADD CONSTRAINT service_equipment_equipment_id_fkey FOREIGN KEY (equipment_id) REFERENCES public.equipment(equipment_id) ON DELETE CASCADE;


--
-- Name: service_equipment service_equipment_supplier_service_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_equipment
    ADD CONSTRAINT service_equipment_supplier_service_id_fkey FOREIGN KEY (supplier_service_id) REFERENCES public.supplier_services(supplier_service_id) ON DELETE CASCADE;


--
-- Name: supplier_profiles supplier_profiles_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_profiles
    ADD CONSTRAINT supplier_profiles_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- Name: supplier_services supplier_services_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_services
    ADD CONSTRAINT supplier_services_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.service_categories(category_id);


--
-- Name: supplier_services supplier_services_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supplier_services
    ADD CONSTRAINT supplier_services_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier_profiles(supplier_id) ON DELETE CASCADE;


--
-- Name: user_capabilities user_capabilities_user_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_capabilities
    ADD CONSTRAINT user_capabilities_user_fk FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--
