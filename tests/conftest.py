"""Shared test fixtures for the Regulatory Knowledge Base test suite."""

import pytest
from regkb.config import Config
from regkb.database import Database


@pytest.fixture
def fresh_config(tmp_path, monkeypatch):
    """Create a Config instance with reset singleton state pointed at a temp directory."""
    Config._instance = None
    monkeypatch.setenv("REGKB_BASE_DIR", str(tmp_path))
    cfg = Config()
    yield cfg
    Config._instance = None


@pytest.fixture
def tmp_db(tmp_path):
    """Create a Database instance using a temp-dir SQLite file."""
    db_path = tmp_path / "test.db"
    return Database(db_path=db_path)


@pytest.fixture
def populated_db(tmp_db):
    """tmp_db with 4 sample documents pre-inserted."""
    tmp_db.add_document(
        file_hash="hash_eu_mdr",
        title="MDR 2017/745 Medical Device Regulation",
        document_type="regulation",
        jurisdiction="EU",
        file_path="/archive/eu/mdr.pdf",
        description="EU Medical Device Regulation",
    )
    tmp_db.add_document(
        file_hash="hash_iso_13485",
        title="ISO 13485:2016 Quality Management Systems",
        document_type="standard",
        jurisdiction="ISO",
        file_path="/archive/iso/13485.pdf",
        description="Quality management systems for medical devices",
    )
    tmp_db.add_document(
        file_hash="hash_fda_qsr",
        title="21 CFR Part 820 Quality System Regulation",
        document_type="regulation",
        jurisdiction="FDA",
        file_path="/archive/fda/qsr.pdf",
        description="FDA Quality System Regulation",
    )
    tmp_db.add_document(
        file_hash="hash_mdcg_2019_11",
        title="MDCG 2019-11 Software Qualification and Classification",
        document_type="guidance",
        jurisdiction="EU",
        file_path="/archive/eu/mdcg_2019_11.pdf",
        description="Guidance on qualification and classification of software",
    )
    return tmp_db
