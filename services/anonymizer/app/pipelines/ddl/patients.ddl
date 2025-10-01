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
