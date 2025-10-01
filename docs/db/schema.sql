-- DROP SCHEMA public;

CREATE SCHEMA public AUTHORIZATION cb_admin;

-- DROP TYPE public."admin_role";

CREATE TYPE public."admin_role" AS ENUM (
	'None',
	'Viewer',
	'Editor',
	'Owner',
	'PrimaryOwner');

-- DROP TYPE public."ai_soap_note_error";

CREATE TYPE public."ai_soap_note_error" AS ENUM (
	'TranscriptToSmall',
	'NoTranscript',
	'APIError',
	'Timeout',
	'Canceled',
	'Unknown');

-- DROP TYPE public."ai_soap_note_status";

CREATE TYPE public."ai_soap_note_status" AS ENUM (
	'Pending',
	'Generating',
	'Generated',
	'Canceled',
	'Error');

-- DROP TYPE public."allergy_category";

CREATE TYPE public."allergy_category" AS ENUM (
	'Drug',
	'Food',
	'Environmental',
	'Substance',
	'Other',
	'Unknown');

-- DROP TYPE public."allergy_clinical_status";

CREATE TYPE public."allergy_clinical_status" AS ENUM (
	'Active',
	'Resolved',
	'PriorHistory',
	'Unknown');

-- DROP TYPE public."allergy_severity";

CREATE TYPE public."allergy_severity" AS ENUM (
	'Mild',
	'Moderate',
	'Severe',
	'Unknown');

-- DROP TYPE public."allergy_type";

CREATE TYPE public."allergy_type" AS ENUM (
	'Allergy',
	'Intolerance',
	'PropensityToAdverseReactions',
	'Unknown');

-- DROP TYPE public."app_platform";

CREATE TYPE public."app_platform" AS ENUM (
	'iOS',
	'Android',
	'Web');

-- DROP TYPE public."app_role";

CREATE TYPE public."app_role" AS ENUM (
	'None',
	'Provider',
	'Nurse');

-- DROP TYPE public."billing_status";

CREATE TYPE public."billing_status" AS ENUM (
	'PendingProvider',
	'SubmittedToQueue',
	'SubmittedToBilling',
	'SubmittedToPayer',
	'Rejected',
	'Denied',
	'Approved',
	'Paid',
	'NotBillable');

-- DROP TYPE public."call_member_notify";

CREATE TYPE public."call_member_notify" AS ENUM (
	'None',
	'Push',
	'Ring');

-- DROP TYPE public."call_state";

CREATE TYPE public."call_state" AS ENUM (
	'Ringing',
	'Connected',
	'Completed',
	'Cancelled',
	'Missed',
	'Rejected');

-- DROP TYPE public."call_type";

CREATE TYPE public."call_type" AS ENUM (
	'Consultation',
	'Chat');

-- DROP TYPE public."condition_clinical_status";

CREATE TYPE public."condition_clinical_status" AS ENUM (
	'Active',
	'Resolved',
	'Unknown');

-- DROP TYPE public."consultation_call_request_state";

CREATE TYPE public."consultation_call_request_state" AS ENUM (
	'Waiting',
	'Ringing',
	'Connected',
	'Completed',
	'Cancelled',
	'Missed',
	'Rejected');

-- DROP TYPE public."consultation_type";

CREATE TYPE public."consultation_type" AS ENUM (
	'VideoCall',
	'InPerson');

-- DROP TYPE public."ehr_connection_status";

CREATE TYPE public."ehr_connection_status" AS ENUM (
	'Connected',
	'Disconnected');

-- DROP TYPE public."ehr_type";

CREATE TYPE public."ehr_type" AS ENUM (
	'PointClickCare',
	'PointClickCareSandbox');

-- DROP TYPE public."facility_status";

CREATE TYPE public."facility_status" AS ENUM (
	'Active',
	'Inactive');

-- DROP TYPE public."gender";

CREATE TYPE public."gender" AS ENUM (
	'male',
	'female',
	'unknown');

-- DROP TYPE public."medication_status";

CREATE TYPE public."medication_status" AS ENUM (
	'Initial',
	'Active',
	'OnHold',
	'Completed',
	'Discontinued',
	'StruckOut',
	'Unverified',
	'Unconfirmed',
	'PendingReview',
	'PendingMarkToSign',
	'PendingSignature',
	'Historical',
	'Draft',
	'Unknown');

-- DROP TYPE public."patient_status";

CREATE TYPE public."patient_status" AS ENUM (
	'Active',
	'Discharged',
	'Pending',
	'Unknown');

-- DROP TYPE public."payer_type";

CREATE TYPE public."payer_type" AS ENUM (
	'ManagedCare',
	'Medicaid',
	'MedicareA',
	'MedicareB',
	'MedicareD',
	'Other',
	'Outpatient',
	'Private',
	'Unknown');

-- DROP TYPE public."provider_on_call_schedule_status";

CREATE TYPE public."provider_on_call_schedule_status" AS ENUM (
	'Active',
	'Archived');

-- DROP TYPE public."suggested_confidence";

CREATE TYPE public."suggested_confidence" AS ENUM (
	'low',
	'medium',
	'high');

-- DROP TYPE public."tenant_facility_access_type";

CREATE TYPE public."tenant_facility_access_type" AS ENUM (
	'Granted',
	'Denied');

-- DROP TYPE public."tenant_status";

CREATE TYPE public."tenant_status" AS ENUM (
	'Active',
	'Inactive');

-- DROP TYPE public."tenant_type";

CREATE TYPE public."tenant_type" AS ENUM (
	'SNFGroup',
	'ProviderGroup',
	'Carebrain');

-- DROP TYPE public."transcription_status";

CREATE TYPE public."transcription_status" AS ENUM (
	'Pending',
	'Ready',
	'Failed',
	'Disabled',
	'NoCall');

-- DROP TYPE public."user_facility_access_type";

CREATE TYPE public."user_facility_access_type" AS ENUM (
	'Granted',
	'Denied');

-- DROP TYPE public."user_notification_type";

CREATE TYPE public."user_notification_type" AS ENUM (
	'CallMissed',
	'CallIncoming',
	'ShiftChange');

-- DROP TYPE public."user_status";

CREATE TYPE public."user_status" AS ENUM (
	'Active',
	'Deactivated',
	'Invited',
	'SoftDeleted');

-- DROP SEQUENCE public.migrations_id_seq;

CREATE SEQUENCE public.migrations_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 2147483647
	START 1
	CACHE 1
	NO CYCLE;-- public.app_release definition

-- Drop table

-- DROP TABLE public.app_release;

CREATE TABLE public.app_release (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	platform public."app_platform" NOT NULL,
	"version" text NOT NULL,
	patch_rev numeric DEFAULT 0 NOT NULL,
	eas_patch text NULL,
	changelog_html text NOT NULL,
	"notify" bool NOT NULL,
	released_at timestamp NULL,
	deprecated_at timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT app_release_patch_rev_check CHECK ((patch_rev >= (0)::numeric)),
	CONSTRAINT app_release_pkey PRIMARY KEY (id),
	CONSTRAINT app_version_unique UNIQUE (platform, version, patch_rev)
);


-- public.demo_instance definition

-- Drop table

-- DROP TABLE public.demo_instance;

CREATE TABLE public.demo_instance (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	"name" text NOT NULL,
	alias text NOT NULL,
	description text NULL,
	tags _text DEFAULT '{}'::text[] NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT demo_instance_alias_key UNIQUE (alias),
	CONSTRAINT demo_instance_pkey PRIMARY KEY (id)
);


-- public.migrations definition

-- Drop table

-- DROP TABLE public.migrations;

CREATE TABLE public.migrations (
	id serial4 NOT NULL,
	"timestamp" int8 NOT NULL,
	"name" varchar NOT NULL,
	CONSTRAINT "PK_8c82d7f526340ab734260ea46be" PRIMARY KEY (id)
);


-- public.pcc_webhook_event_log definition

-- Drop table

-- DROP TABLE public.pcc_webhook_event_log;

CREATE TABLE public.pcc_webhook_event_log (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	log jsonb NULL,
	processed_at timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT pcc_webhook_event_log_pkey PRIMARY KEY (id)
);
CREATE INDEX pcc_webhook_event_log_message_id_unique ON public.pcc_webhook_event_log USING btree (((log ->> 'messageId'::text)));


-- public.pcc_webhook_event_log_sandbox definition

-- Drop table

-- DROP TABLE public.pcc_webhook_event_log_sandbox;

CREATE TABLE public.pcc_webhook_event_log_sandbox (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	log jsonb NULL,
	processed_at timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT pcc_webhook_event_log_sandbox_pkey PRIMARY KEY (id)
);
CREATE INDEX pcc_webhook_event_log_sandbox_message_id_unique ON public.pcc_webhook_event_log_sandbox USING btree (((log ->> 'messageId'::text)));


-- public.tenant definition

-- Drop table

-- DROP TABLE public.tenant;

CREATE TABLE public.tenant (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	auth_id text NOT NULL,
	"name" text NOT NULL,
	"type" public."tenant_type" NOT NULL,
	logo_url text NULL,
	status public."tenant_status" DEFAULT 'Active'::tenant_status NOT NULL,
	candid_instance_id text NULL,
	tags _text DEFAULT '{}'::text[] NOT NULL,
	demo_instance_id uuid NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT tenant_auth_id_key UNIQUE (auth_id),
	CONSTRAINT tenant_pkey PRIMARY KEY (id),
	CONSTRAINT tenant_demo_instance_id_fkey FOREIGN KEY (demo_instance_id) REFERENCES public.demo_instance(id) ON DELETE CASCADE
);


-- public.ehr_instance definition

-- Drop table

-- DROP TABLE public.ehr_instance;

CREATE TABLE public.ehr_instance (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NULL,
	status public."ehr_connection_status" DEFAULT 'Connected'::ehr_connection_status NOT NULL,
	"type" public."ehr_type" NOT NULL,
	org_id text NOT NULL,
	"name" text NOT NULL,
	metadata jsonb NULL,
	last_manual_facilities_sync_at timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT ehr_instance_pkey PRIMARY KEY (id),
	CONSTRAINT ehr_instance_unique UNIQUE (type, org_id),
	CONSTRAINT ehr_instance_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public.patient_consent_form definition

-- Drop table

-- DROP TABLE public.patient_consent_form;

CREATE TABLE public.patient_consent_form (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	"name" text NOT NULL,
	"content" text NOT NULL,
	is_archived bool DEFAULT false NOT NULL,
	is_default bool DEFAULT false NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_consent_form_archived_check CHECK ((((is_archived = true) AND (is_default = false)) OR (is_archived = false))),
	CONSTRAINT patient_consent_form_pkey PRIMARY KEY (id),
	CONSTRAINT patient_consent_form_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX patient_consent_form_default_unique ON public.patient_consent_form USING btree (tenant_id) WHERE (is_default = true);


-- public.provider_on_call_schedule definition

-- Drop table

-- DROP TABLE public.provider_on_call_schedule;

CREATE TABLE public.provider_on_call_schedule (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	status public."provider_on_call_schedule_status" DEFAULT 'Active'::provider_on_call_schedule_status NOT NULL,
	"name" text NOT NULL,
	timezone text NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_on_call_schedule_pkey PRIMARY KEY (id),
	CONSTRAINT provider_on_call_schedule_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public.provider_on_call_schedule_shift_definition definition

-- Drop table

-- DROP TABLE public.provider_on_call_schedule_shift_definition;

CREATE TABLE public.provider_on_call_schedule_shift_definition (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	provider_on_call_schedule_id uuid NOT NULL,
	"name" text NOT NULL,
	start_time text NOT NULL,
	end_time text NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_on_call_schedule_shift_definition_pkey PRIMARY KEY (id),
	CONSTRAINT provider_on_call_schedule_shi_provider_on_call_schedule_id_fkey FOREIGN KEY (provider_on_call_schedule_id) REFERENCES public.provider_on_call_schedule(id) ON DELETE CASCADE
);


-- public.facility definition

-- Drop table

-- DROP TABLE public.facility;

CREATE TABLE public.facility (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	ehr_last_manual_patients_sync_at timestamp NULL,
	provider_on_call_schedule_id uuid NULL,
	patient_consent_form_id uuid NULL,
	status public."facility_status" NOT NULL,
	"name" text NOT NULL,
	address jsonb NULL,
	bed_count int4 NULL,
	health_type text NULL,
	timezone text NULL,
	contact_email text NULL,
	contact_phone text NULL,
	inactive_date date NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT facility_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT facility_inactive_date_check CHECK ((((status = 'Inactive'::facility_status) AND (inactive_date IS NOT NULL)) OR (status <> 'Inactive'::facility_status))),
	CONSTRAINT facility_pkey PRIMARY KEY (id),
	CONSTRAINT facility_unique UNIQUE (tenant_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT facility_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT facility_patient_consent_form_id_fkey FOREIGN KEY (patient_consent_form_id) REFERENCES public.patient_consent_form(id),
	CONSTRAINT facility_provider_on_call_schedule_id_fkey FOREIGN KEY (provider_on_call_schedule_id) REFERENCES public.provider_on_call_schedule(id),
	CONSTRAINT facility_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public.facility_candid_billing_info definition

-- Drop table

-- DROP TABLE public.facility_candid_billing_info;

CREATE TABLE public.facility_candid_billing_info (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	candid_billing_provider_id text NOT NULL,
	candid_service_facility_id text NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT facility_candid_billing_info_pkey PRIMARY KEY (id),
	CONSTRAINT provider_group_facility_billing_info_facility_unique UNIQUE (tenant_id, facility_id),
	CONSTRAINT facility_candid_billing_info_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT facility_candid_billing_info_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public.patient definition

-- Drop table

-- DROP TABLE public.patient;

CREATE TABLE public.patient (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	ehr_last_full_manual_sync_at timestamp NULL,
	name_first text NOT NULL,
	name_last text NOT NULL,
	dob date NULL,
	"gender" public."gender" NOT NULL,
	ethnicity_description text NULL,
	legal_mailing_address jsonb NULL,
	photo_url text NULL,
	unit_description text NULL,
	floor_description text NULL,
	room_description text NULL,
	bed_description text NULL,
	status public."patient_status" NOT NULL,
	admission_time timestamp NULL,
	discharge_time timestamp NULL,
	death_time timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT patient_pkey PRIMARY KEY (id),
	CONSTRAINT patient_unique UNIQUE (facility_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT patient_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT patient_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT patient_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public.patient_allergy definition

-- Drop table

-- DROP TABLE public.patient_allergy;

CREATE TABLE public.patient_allergy (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	patient_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	allergen text NOT NULL,
	category public."allergy_category" DEFAULT 'Unknown'::allergy_category NOT NULL,
	clinical_status public."allergy_clinical_status" NOT NULL,
	created_by text NULL,
	created_time timestamp NULL,
	onset_date date NULL,
	reaction_note text NULL,
	reaction_type text NULL,
	reaction_sub_type text NULL,
	resolved_date date NULL,
	rev_by text NULL,
	rev_time timestamp NULL,
	severity public."allergy_severity" DEFAULT 'Unknown'::allergy_severity NOT NULL,
	"type" public."allergy_type" DEFAULT 'Unknown'::allergy_type NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_allergy_pkey PRIMARY KEY (id),
	CONSTRAINT patient_allergy_unique UNIQUE (patient_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT patient_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT patient_allergy_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT patient_allergy_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE CASCADE
);


-- public.patient_condition definition

-- Drop table

-- DROP TABLE public.patient_condition;

CREATE TABLE public.patient_condition (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	patient_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	classification_description text NULL,
	clinical_status public."condition_clinical_status" NOT NULL,
	"comments" text NULL,
	created_by text NULL,
	created_time timestamp NULL,
	icd_10_code text NULL,
	icd_10_description text NULL,
	onset_date date NULL,
	is_primary_diagnosis bool NOT NULL,
	resolved_date date NULL,
	rev_by text NULL,
	rev_time timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_condition_pkey PRIMARY KEY (id),
	CONSTRAINT patient_condition_unique UNIQUE (patient_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT patient_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT patient_condition_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT patient_condition_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE CASCADE
);


-- public.patient_coverage definition

-- Drop table

-- DROP TABLE public.patient_coverage;

CREATE TABLE public.patient_coverage (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	patient_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	payer_name text NOT NULL,
	"payer_type" public."payer_type" NOT NULL,
	payer_rank int4 NOT NULL,
	payer_code text NULL,
	payer_code_2 text NULL,
	informational_only bool DEFAULT false NOT NULL,
	effective_time timestamp NOT NULL,
	expiration_time timestamp NULL,
	account_number text NULL,
	account_description text NULL,
	issuer jsonb NULL,
	insured_party jsonb NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_coverage_pkey PRIMARY KEY (id),
	CONSTRAINT patient_coverage_unique UNIQUE (patient_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT patient_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT patient_coverage_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT patient_coverage_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE CASCADE
);


-- public.patient_medication definition

-- Drop table

-- DROP TABLE public.patient_medication;

CREATE TABLE public.patient_medication (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	patient_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	created_by text NULL,
	created_time timestamp NULL,
	description text DEFAULT 'Missing'::text NOT NULL,
	directions text DEFAULT 'Missing'::text NOT NULL,
	discontinued_time timestamp NULL,
	end_time date NULL,
	generic_name text NULL,
	narcotic bool NULL,
	order_time timestamp NULL,
	physician_details jsonb NULL,
	rev_by text NULL,
	rev_time timestamp NULL,
	rx_norm_id text NULL,
	start_time date NULL,
	status public."medication_status" NOT NULL,
	strength text NULL,
	strength_unit text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT patient_medication_pkey PRIMARY KEY (id),
	CONSTRAINT patient_medication_unique UNIQUE (patient_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT patient_medication_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT patient_medication_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE CASCADE
);


-- public.patient_observation definition

-- Drop table

-- DROP TABLE public.patient_observation;

CREATE TABLE public.patient_observation (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	patient_id uuid NOT NULL,
	ehr_instance_id uuid NULL,
	ehr_external_id text NULL,
	"ehr_connection_status" public."ehr_connection_status" NULL,
	"method" text NULL,
	recorded_by text NULL,
	recorded_time timestamp NULL,
	"data" jsonb NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT patient_ehr_connection_status_check CHECK ((((ehr_connection_status IS NOT NULL) AND (ehr_instance_id IS NOT NULL) AND (ehr_external_id IS NOT NULL)) OR (ehr_connection_status IS NULL))),
	CONSTRAINT patient_observation_pkey PRIMARY KEY (id),
	CONSTRAINT patient_observation_unique UNIQUE (patient_id, ehr_instance_id, ehr_external_id),
	CONSTRAINT patient_observation_ehr_instance_id_fkey FOREIGN KEY (ehr_instance_id) REFERENCES public.ehr_instance(id),
	CONSTRAINT patient_observation_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE CASCADE
);


-- public.tenant_facility_access definition

-- Drop table

-- DROP TABLE public.tenant_facility_access;

CREATE TABLE public.tenant_facility_access (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	"access" public."tenant_facility_access_type" DEFAULT 'Denied'::tenant_facility_access_type NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT tenant_facility_access_pkey PRIMARY KEY (id),
	CONSTRAINT tenant_facility_access_unique UNIQUE (tenant_id, facility_id),
	CONSTRAINT tenant_facility_access_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT tenant_facility_access_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public."user" definition

-- Drop table

-- DROP TABLE public."user";

CREATE TABLE public."user" (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	tenant_id uuid NOT NULL,
	default_facility_id uuid NULL,
	status public."user_status" NOT NULL,
	"app_role" public."app_role" DEFAULT 'None'::app_role NOT NULL,
	"admin_role" public."admin_role" DEFAULT 'None'::admin_role NOT NULL,
	name_first text NOT NULL,
	name_last text NOT NULL,
	email text NULL,
	phone text NULL,
	timezone text NULL,
	photo_url text NULL,
	title text NULL,
	"position" text NULL,
	caller_pin_code text NULL,
	clinician_metadata jsonb NULL,
	stream_metadata jsonb NULL,
	complete_account_token_expiry_date timestamp NULL,
	complete_account_token text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	complete_account_at timestamp NULL,
	deactivated_at timestamp NULL,
	CONSTRAINT user_email_key UNIQUE (email),
	CONSTRAINT user_phone_key UNIQUE (phone),
	CONSTRAINT user_pkey PRIMARY KEY (id),
	CONSTRAINT user_status_check CHECK ((((status = 'Invited'::user_status) AND (complete_account_token IS NOT NULL) AND (complete_account_token_expiry_date IS NOT NULL) AND (complete_account_at IS NULL) AND (deactivated_at IS NULL)) OR ((status = 'Active'::user_status) AND (complete_account_at IS NOT NULL) AND (deactivated_at IS NULL)) OR ((status = 'Deactivated'::user_status) AND (deactivated_at IS NOT NULL)) OR ((status = 'SoftDeleted'::user_status) AND (deactivated_at IS NOT NULL)))),
	CONSTRAINT user_default_facility_id_fkey FOREIGN KEY (default_facility_id) REFERENCES public.facility(id),
	CONSTRAINT user_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE
);


-- public.user_facility_access definition

-- Drop table

-- DROP TABLE public.user_facility_access;

CREATE TABLE public.user_facility_access (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	facility_id uuid NOT NULL,
	user_id uuid NOT NULL,
	"access" public."user_facility_access_type" DEFAULT 'Denied'::user_facility_access_type NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT user_facility_access_pkey PRIMARY KEY (id),
	CONSTRAINT user_facility_access_unique UNIQUE (user_id, facility_id),
	CONSTRAINT user_facility_access_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT user_facility_access_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.user_login_provider definition

-- Drop table

-- DROP TABLE public.user_login_provider;

CREATE TABLE public.user_login_provider (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	user_id uuid NOT NULL,
	details jsonb NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT user_login_provider_pkey PRIMARY KEY (id),
	CONSTRAINT user_login_provider_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX user_login_provider_user_type_unique ON public.user_login_provider USING btree (user_id, ((details ->> 'type'::text)));


-- public.user_notification definition

-- Drop table

-- DROP TABLE public.user_notification;

CREATE TABLE public.user_notification (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	user_id uuid NOT NULL,
	"type" public."user_notification_type" NOT NULL,
	in_app bool DEFAULT false NOT NULL,
	email bool DEFAULT false NOT NULL,
	phone_text bool DEFAULT false NOT NULL,
	phone_voice bool DEFAULT false NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT user_notification_pkey PRIMARY KEY (id),
	CONSTRAINT user_notification_unique UNIQUE (user_id, type),
	CONSTRAINT user_notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.user_session definition

-- Drop table

-- DROP TABLE public.user_session;

CREATE TABLE public.user_session (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	user_id uuid NOT NULL,
	user_login_provider_id uuid NOT NULL,
	auth_time timestamp NULL,
	expires_at timestamp NOT NULL,
	revoked_at timestamp NULL,
	firebase jsonb NULL,
	provider_details jsonb NOT NULL,
	ip_address text NULL,
	user_agent text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT user_session_pkey PRIMARY KEY (id),
	CONSTRAINT user_session_unique UNIQUE (user_id, auth_time),
	CONSTRAINT user_session_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE,
	CONSTRAINT user_session_user_login_provider_id_fkey FOREIGN KEY (user_login_provider_id) REFERENCES public.user_login_provider(id) ON DELETE CASCADE
);


-- public."call" definition

-- Drop table

-- DROP TABLE public."call";

CREATE TABLE public."call" (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	"type" public."call_type" NOT NULL,
	stream_call_type text NOT NULL,
	caller_user_id uuid NOT NULL,
	active bool DEFAULT true NOT NULL,
	state public."call_state" NOT NULL,
	started_at timestamp NULL,
	finished_at timestamp NULL,
	"transcription_status" public."transcription_status" NOT NULL,
	transcription_storage_url text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT call_accepted_check CHECK ((((state = ANY (ARRAY['Ringing'::call_state, 'Cancelled'::call_state, 'Missed'::call_state, 'Rejected'::call_state])) AND (started_at IS NULL)) OR ((state = ANY (ARRAY['Connected'::call_state, 'Completed'::call_state])) AND (started_at IS NOT NULL)))),
	CONSTRAINT call_finished_check CHECK ((((state = ANY (ARRAY['Ringing'::call_state, 'Connected'::call_state])) AND (finished_at IS NULL)) OR ((state = ANY (ARRAY['Completed'::call_state, 'Cancelled'::call_state, 'Missed'::call_state, 'Rejected'::call_state])) AND (finished_at IS NOT NULL)))),
	CONSTRAINT call_pkey PRIMARY KEY (id),
	CONSTRAINT call_state_check CHECK ((((state = ANY (ARRAY['Ringing'::call_state, 'Connected'::call_state])) AND (active = true)) OR ((state = ANY (ARRAY['Completed'::call_state, 'Cancelled'::call_state, 'Missed'::call_state, 'Rejected'::call_state])) AND (active = false)))),
	CONSTRAINT call_transcription_status_check CHECK ((((transcription_status = 'Ready'::transcription_status) AND (transcription_storage_url IS NOT NULL)) OR (((transcription_status = ANY (ARRAY['Pending'::transcription_status, 'Failed'::transcription_status, 'NoCall'::transcription_status, 'Disabled'::transcription_status])) OR (transcription_status IS NULL)) AND (transcription_storage_url IS NULL)))),
	CONSTRAINT call_caller_user_id_fkey FOREIGN KEY (caller_user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);

-- Table Triggers

create trigger trigger_notify_call_updated after
insert
    or
update
    on
    public.call for each row execute function notify_call_updated();


-- public.call_feedback definition

-- Drop table

-- DROP TABLE public.call_feedback;

CREATE TABLE public.call_feedback (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	call_id uuid NOT NULL,
	user_id uuid NOT NULL,
	rating numeric NOT NULL,
	tags _text NULL,
	"comment" text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT call_feedback_pkey PRIMARY KEY (id),
	CONSTRAINT call_feedback_rating_check CHECK (((rating >= (1)::numeric) AND (rating <= (5)::numeric))),
	CONSTRAINT call_feedback_unique UNIQUE (call_id, user_id),
	CONSTRAINT call_feedback_call_id_fkey FOREIGN KEY (call_id) REFERENCES public."call"(id) ON DELETE CASCADE,
	CONSTRAINT call_feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.call_member definition

-- Drop table

-- DROP TABLE public.call_member;

CREATE TABLE public.call_member (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	call_id uuid NOT NULL,
	user_id uuid NOT NULL,
	accepted_at timestamp NULL,
	"notify" public."call_member_notify" DEFAULT 'None'::call_member_notify NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT call_member_pkey PRIMARY KEY (id),
	CONSTRAINT call_member_unique UNIQUE (call_id, user_id),
	CONSTRAINT call_member_call_id_fkey FOREIGN KEY (call_id) REFERENCES public."call"(id) ON DELETE CASCADE,
	CONSTRAINT call_member_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.call_user_app_metadata definition

-- Drop table

-- DROP TABLE public.call_user_app_metadata;

CREATE TABLE public.call_user_app_metadata (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	call_id uuid NOT NULL,
	user_id uuid NOT NULL,
	platform public."app_platform" NOT NULL,
	"version" text NOT NULL,
	patch text NULL,
	logrocket_url text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT call_user_app_metadata_pkey PRIMARY KEY (id),
	CONSTRAINT call_user_app_metadata_unique UNIQUE (call_id, user_id, platform, version, patch, logrocket_url),
	CONSTRAINT call_user_app_metadata_call_id_fkey FOREIGN KEY (call_id) REFERENCES public."call"(id) ON DELETE CASCADE,
	CONSTRAINT call_user_app_metadata_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.consultation definition

-- Drop table

-- DROP TABLE public.consultation;

CREATE TABLE public.consultation (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	"type" public."consultation_type" DEFAULT 'VideoCall'::consultation_type NOT NULL,
	patient_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	nurse_user_id uuid NULL,
	provider_user_id uuid NULL,
	chief_complaint text NULL,
	patient_consent_timestamp timestamp NULL,
	pertinent_exam jsonb NULL,
	short_note text NULL,
	soap_note text NULL,
	ai_soap_note text NULL,
	"ai_soap_note_status" public."ai_soap_note_status" DEFAULT 'Pending'::ai_soap_note_status NOT NULL,
	"ai_soap_note_error" public."ai_soap_note_error" NULL,
	order_text text NULL,
	order_placed_at timestamp NULL,
	order_confirmed_at timestamp NULL,
	provider_signed_at timestamp NULL,
	"billing_status" public."billing_status" DEFAULT 'PendingProvider'::billing_status NOT NULL,
	billing_submitted_at timestamp NULL,
	billing_issues _text NULL,
	billing_amount numeric NULL,
	candid_instance_id text NULL,
	candid_encounter_id text NULL,
	slack_thread_ts text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT ai_soap_note_status_check CHECK ((((ai_soap_note_status = 'Generated'::ai_soap_note_status) AND (ai_soap_note IS NOT NULL)) OR ((ai_soap_note_status <> 'Generated'::ai_soap_note_status) AND (ai_soap_note IS NULL)))),
	CONSTRAINT consultation_pkey PRIMARY KEY (id),
	CONSTRAINT consultation_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT consultation_nurse_user_id_fkey FOREIGN KEY (nurse_user_id) REFERENCES public."user"(id) ON DELETE CASCADE,
	CONSTRAINT consultation_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES public.patient(id) ON DELETE CASCADE,
	CONSTRAINT consultation_provider_user_id_fkey FOREIGN KEY (provider_user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);

-- Table Triggers

create trigger trigger_notify_consultation_updated after
insert
    or
update
    on
    public.consultation for each row execute function notify_consultation_updated();


-- public.consultation_billing_code definition

-- Drop table

-- DROP TABLE public.consultation_billing_code;

CREATE TABLE public.consultation_billing_code (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	consultation_id uuid NOT NULL,
	code text NOT NULL,
	description text NOT NULL,
	suggested bool NOT NULL,
	suggested_reason text NULL,
	"suggested_confidence" public."suggested_confidence" NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT consultation_billing_code_pkey PRIMARY KEY (id),
	CONSTRAINT consultation_billing_code_unique UNIQUE (consultation_id, code, suggested),
	CONSTRAINT consultation_billing_code_consultation_id_fkey FOREIGN KEY (consultation_id) REFERENCES public.consultation(id) ON DELETE CASCADE
);


-- public.consultation_call_request definition

-- Drop table

-- DROP TABLE public.consultation_call_request;

CREATE TABLE public.consultation_call_request (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	consultation_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	caller_user_id uuid NOT NULL,
	provider_user_id uuid NULL,
	call_id uuid NULL,
	active bool DEFAULT true NOT NULL,
	state public."consultation_call_request_state" DEFAULT 'Waiting'::consultation_call_request_state NOT NULL,
	finished_at timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT consultation_call_request_pkey PRIMARY KEY (id),
	CONSTRAINT consultation_call_request_state_check CHECK ((((state = ANY (ARRAY['Completed'::consultation_call_request_state, 'Cancelled'::consultation_call_request_state, 'Missed'::consultation_call_request_state, 'Rejected'::consultation_call_request_state])) AND (active = false)) OR ((state = ANY (ARRAY['Waiting'::consultation_call_request_state, 'Ringing'::consultation_call_request_state, 'Connected'::consultation_call_request_state])) AND (active = true)))),
	CONSTRAINT consultation_call_request_call_id_fkey FOREIGN KEY (call_id) REFERENCES public."call"(id) ON DELETE CASCADE,
	CONSTRAINT consultation_call_request_caller_user_id_fkey FOREIGN KEY (caller_user_id) REFERENCES public."user"(id) ON DELETE CASCADE,
	CONSTRAINT consultation_call_request_consultation_id_fkey FOREIGN KEY (consultation_id) REFERENCES public.consultation(id) ON DELETE CASCADE,
	CONSTRAINT consultation_call_request_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT consultation_call_request_provider_user_id_fkey FOREIGN KEY (provider_user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX consultation_call_request_unique_active ON public.consultation_call_request USING btree (consultation_id, active) WHERE (active = true);

-- Table Triggers

create trigger trigger_notify_consultation_call_request_updated after
insert
    or
update
    on
    public.consultation_call_request for each row execute function notify_consultation_call_request_updated();


-- public.consultation_icd_10_code definition

-- Drop table

-- DROP TABLE public.consultation_icd_10_code;

CREATE TABLE public.consultation_icd_10_code (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	consultation_id uuid NOT NULL,
	associated_billing_code_id uuid NULL,
	code text NOT NULL,
	"name" text NOT NULL,
	suggested bool NOT NULL,
	suggested_reason text NULL,
	"suggested_confidence" public."suggested_confidence" NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT consultation_icd_10_code_pkey PRIMARY KEY (id),
	CONSTRAINT consultation_icd_10_code_unique UNIQUE (consultation_id, code, suggested),
	CONSTRAINT consultation_icd_10_code_associated_billing_code_id_fkey FOREIGN KEY (associated_billing_code_id) REFERENCES public.consultation_billing_code(id),
	CONSTRAINT consultation_icd_10_code_consultation_id_fkey FOREIGN KEY (consultation_id) REFERENCES public.consultation(id) ON DELETE CASCADE
);


-- public.provider_busy definition

-- Drop table

-- DROP TABLE public.provider_busy;

CREATE TABLE public.provider_busy (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	user_id uuid NOT NULL,
	call_finished_at timestamp NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_busy_pkey PRIMARY KEY (id),
	CONSTRAINT provider_busy_user_id_key UNIQUE (user_id),
	CONSTRAINT provider_busy_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.provider_candid_info definition

-- Drop table

-- DROP TABLE public.provider_candid_info;

CREATE TABLE public.provider_candid_info (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	user_id uuid NOT NULL,
	candid_provider_id text NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_candid_info_pkey PRIMARY KEY (id),
	CONSTRAINT provider_candid_info_user_id_key UNIQUE (user_id),
	CONSTRAINT provider_candid_info_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.provider_on_call_facility_manual definition

-- Drop table

-- DROP TABLE public.provider_on_call_facility_manual;

CREATE TABLE public.provider_on_call_facility_manual (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	user_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	enabled bool DEFAULT false NOT NULL,
	"rank" int4 NOT NULL,
	last_ringed_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_on_call_facility_manual_pkey PRIMARY KEY (id),
	CONSTRAINT provider_on_call_facility_manual_unique UNIQUE (user_id, facility_id),
	CONSTRAINT provider_on_call_facility_manual_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT provider_on_call_facility_manual_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.provider_on_call_schedule_shift definition

-- Drop table

-- DROP TABLE public.provider_on_call_schedule_shift;

CREATE TABLE public.provider_on_call_schedule_shift (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	provider_on_call_schedule_id uuid NOT NULL,
	provider_on_call_schedule_shift_definition_id uuid NOT NULL,
	provider_user_id uuid NOT NULL,
	"date" date NOT NULL,
	start_time timestamptz NOT NULL,
	end_time timestamptz NOT NULL,
	is_primary bool DEFAULT false NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_on_call_schedule_shift_pkey PRIMARY KEY (id),
	CONSTRAINT provider_on_call_schedule_shift_provider_unique UNIQUE (provider_user_id, date, provider_on_call_schedule_shift_definition_id),
	CONSTRAINT provider_on_call_schedule_sh_provider_on_call_schedule_id_fkey1 FOREIGN KEY (provider_on_call_schedule_id) REFERENCES public.provider_on_call_schedule(id) ON DELETE CASCADE,
	CONSTRAINT provider_on_call_schedule_shi_provider_on_call_schedule_sh_fkey FOREIGN KEY (provider_on_call_schedule_shift_definition_id) REFERENCES public.provider_on_call_schedule_shift_definition(id) ON DELETE CASCADE,
	CONSTRAINT provider_on_call_schedule_shift_provider_user_id_fkey FOREIGN KEY (provider_user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);


-- public.provider_on_call_facility_scheduled definition

-- Drop table

-- DROP TABLE public.provider_on_call_facility_scheduled;

CREATE TABLE public.provider_on_call_facility_scheduled (
	id uuid DEFAULT uuid_generate_v4() NOT NULL,
	provider_on_call_schedule_shift_id uuid NOT NULL,
	user_id uuid NOT NULL,
	facility_id uuid NOT NULL,
	"rank" int4 NOT NULL,
	last_ringed_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT provider_on_call_facility_scheduled_pkey PRIMARY KEY (id),
	CONSTRAINT provider_on_call_facility_scheduled_unique UNIQUE (user_id, facility_id),
	CONSTRAINT provider_on_call_facility_sch_provider_on_call_schedule_sh_fkey FOREIGN KEY (provider_on_call_schedule_shift_id) REFERENCES public.provider_on_call_schedule_shift(id) ON DELETE CASCADE,
	CONSTRAINT provider_on_call_facility_scheduled_facility_id_fkey FOREIGN KEY (facility_id) REFERENCES public.facility(id) ON DELETE CASCADE,
	CONSTRAINT provider_on_call_facility_scheduled_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE
);



-- DROP FUNCTION public.notify_call_updated();

CREATE OR REPLACE FUNCTION public.notify_call_updated()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  PERFORM pg_notify('call_updated', row_to_json(NEW)::text);
  RETURN NEW;
END;
$function$
;

-- DROP FUNCTION public.notify_consultation_call_request_updated();

CREATE OR REPLACE FUNCTION public.notify_consultation_call_request_updated()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  PERFORM pg_notify('consultation_call_request_updated', row_to_json(NEW)::text);
  RETURN NEW;
END;
$function$
;

-- DROP FUNCTION public.notify_consultation_updated();

CREATE OR REPLACE FUNCTION public.notify_consultation_updated()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  PERFORM pg_notify('consultation_updated', row_to_json(NEW)::text);
  RETURN NEW;
END;
$function$
;

-- DROP FUNCTION public.uuid_generate_v1();

CREATE OR REPLACE FUNCTION public.uuid_generate_v1()
 RETURNS uuid
 LANGUAGE c
 PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_generate_v1$function$
;

-- DROP FUNCTION public.uuid_generate_v1mc();

CREATE OR REPLACE FUNCTION public.uuid_generate_v1mc()
 RETURNS uuid
 LANGUAGE c
 PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_generate_v1mc$function$
;

-- DROP FUNCTION public.uuid_generate_v3(uuid, text);

CREATE OR REPLACE FUNCTION public.uuid_generate_v3(namespace uuid, name text)
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_generate_v3$function$
;

-- DROP FUNCTION public.uuid_generate_v4();

CREATE OR REPLACE FUNCTION public.uuid_generate_v4()
 RETURNS uuid
 LANGUAGE c
 PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_generate_v4$function$
;

-- DROP FUNCTION public.uuid_generate_v5(uuid, text);

CREATE OR REPLACE FUNCTION public.uuid_generate_v5(namespace uuid, name text)
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_generate_v5$function$
;

-- DROP FUNCTION public.uuid_nil();

CREATE OR REPLACE FUNCTION public.uuid_nil()
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_nil$function$
;

-- DROP FUNCTION public.uuid_ns_dns();

CREATE OR REPLACE FUNCTION public.uuid_ns_dns()
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_ns_dns$function$
;

-- DROP FUNCTION public.uuid_ns_oid();

CREATE OR REPLACE FUNCTION public.uuid_ns_oid()
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_ns_oid$function$
;

-- DROP FUNCTION public.uuid_ns_url();

CREATE OR REPLACE FUNCTION public.uuid_ns_url()
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_ns_url$function$
;

-- DROP FUNCTION public.uuid_ns_x500();

CREATE OR REPLACE FUNCTION public.uuid_ns_x500()
 RETURNS uuid
 LANGUAGE c
 IMMUTABLE PARALLEL SAFE STRICT
AS '$libdir/uuid-ossp', $function$uuid_ns_x500$function$
;