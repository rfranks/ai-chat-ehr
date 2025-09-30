"""Tests for the anonymizer DDL parser."""

from pathlib import Path

from services.anonymizer.app.pipelines.ddl_parser import (
    build_insert_statement,
    build_mapping_from_files,
    load_table_metadata,
    parse_ddl,
)

PATIENT_DDL = """\
CREATE TABLE public.patient (
    id uuid DEFAULT uuid_generate_v4() NOT NULL,
    tenant_id uuid NOT NULL,
    facility_id uuid NOT NULL,
    ehr_instance_id uuid NULL,
    CONSTRAINT patient_pkey PRIMARY KEY (id)
);
"""


def test_parse_ddl_extracts_table_metadata(tmp_path: Path) -> None:
    ddl_file = tmp_path / "patient.ddl"
    ddl_file.write_text(PATIENT_DDL)

    metadata = load_table_metadata(ddl_file)

    assert metadata.schema == "public"
    assert metadata.name == "patient"
    assert metadata.fully_qualified_name == "public.patient"

    column_names = [column.name for column in metadata.columns]
    assert column_names == ["id", "tenant_id", "facility_id", "ehr_instance_id"]

    id_column = metadata.columns[0]
    assert id_column.data_type == "uuid"
    assert id_column.default == "uuid_generate_v4()"
    assert id_column.nullable is False
    assert id_column.has_default is True

    nullable_column = metadata.columns[-1]
    assert nullable_column.nullable is True

    assert metadata.required_columns() == ("tenant_id", "facility_id")
    assert metadata.optional_columns() == ("id", "ehr_instance_id")


def test_build_insert_statement_controls_selected_columns() -> None:
    metadata = parse_ddl(PATIENT_DDL)

    statement = build_insert_statement(metadata, include_defaulted=False)
    assert statement.table == "public.patient"
    assert statement.columns == ("tenant_id", "facility_id", "ehr_instance_id")

    no_nullable = build_insert_statement(metadata, include_nullable=False)
    assert no_nullable.columns == ("id", "tenant_id", "facility_id")


def test_build_mapping_from_files_supports_iterables(tmp_path: Path) -> None:
    ddl_file = tmp_path / "patient.ddl"
    ddl_file.write_text(PATIENT_DDL)

    mapping = build_mapping_from_files([ddl_file], include_defaulted=False)

    assert set(mapping.keys()) == {"patient"}
    statement = mapping["patient"]
    assert statement.columns == ("tenant_id", "facility_id", "ehr_instance_id")


def test_build_mapping_from_files_supports_mapping(tmp_path: Path) -> None:
    ddl_file = tmp_path / "custom_patient.ddl"
    ddl_file.write_text(PATIENT_DDL)

    mapping = build_mapping_from_files({"patients": ddl_file}, include_defaulted=False)

    assert "patients" in mapping
    statement = mapping["patients"]
    assert statement.columns == ("tenant_id", "facility_id", "ehr_instance_id")
