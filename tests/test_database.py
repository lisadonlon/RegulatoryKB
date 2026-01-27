"""Integration tests with temp SQLite database."""


class TestAddAndGetDocument:
    def test_round_trip(self, tmp_db):
        doc_id = tmp_db.add_document(
            file_hash="abc123",
            title="Test Document",
            document_type="guidance",
            jurisdiction="EU",
            file_path="/test/path.pdf",
            description="A test document",
        )
        doc = tmp_db.get_document(doc_id=doc_id)
        assert doc is not None
        assert doc["title"] == "Test Document"
        assert doc["document_type"] == "guidance"
        assert doc["jurisdiction"] == "EU"
        assert doc["hash"] == "abc123"


class TestDocumentExists:
    def test_existing_hash(self, populated_db):
        assert populated_db.document_exists("hash_eu_mdr") is True

    def test_unknown_hash(self, populated_db):
        assert populated_db.document_exists("nonexistent_hash") is False


class TestUpdateDocument:
    def test_update_allowed_fields(self, populated_db):
        doc = populated_db.get_document(file_hash="hash_eu_mdr")
        result = populated_db.update_document(doc["id"], title="Updated Title")
        assert result is True
        updated = populated_db.get_document(doc_id=doc["id"])
        assert updated["title"] == "Updated Title"

    def test_rejects_disallowed_fields(self, populated_db):
        doc = populated_db.get_document(file_hash="hash_eu_mdr")
        result = populated_db.update_document(doc["id"], hash="new_hash")
        assert result is False

    def test_returns_false_on_empty_kwargs(self, populated_db):
        doc = populated_db.get_document(file_hash="hash_eu_mdr")
        result = populated_db.update_document(doc["id"])
        assert result is False


class TestListDocuments:
    def test_filter_by_type(self, populated_db):
        docs = populated_db.list_documents(document_type="regulation")
        assert len(docs) == 2
        assert all(d["document_type"] == "regulation" for d in docs)

    def test_filter_by_jurisdiction(self, populated_db):
        docs = populated_db.list_documents(jurisdiction="EU")
        assert len(docs) == 2
        assert all(d["jurisdiction"] == "EU" for d in docs)

    def test_latest_only(self, populated_db):
        docs = populated_db.list_documents(latest_only=True)
        assert all(d["is_latest"] == 1 for d in docs)

    def test_respects_limit_offset(self, populated_db):
        all_docs = populated_db.list_documents(latest_only=False)
        limited = populated_db.list_documents(limit=2, offset=0, latest_only=False)
        assert len(limited) == 2
        assert len(all_docs) == 4


class TestSearchFts:
    def test_finds_by_title_keyword(self, populated_db):
        results = populated_db.search_fts("Medical Device Regulation")
        assert len(results) >= 1
        titles = [r["title"] for r in results]
        assert any("MDR" in t for t in titles)


class TestGetStatistics:
    def test_correct_counts(self, populated_db):
        stats = populated_db.get_statistics()
        assert stats["total_documents"] == 4
        assert stats["by_type"]["regulation"] == 2
        assert stats["by_type"]["guidance"] == 1
        assert stats["by_type"]["standard"] == 1
        assert stats["by_jurisdiction"]["EU"] == 2
        assert stats["by_jurisdiction"]["ISO"] == 1
        assert stats["by_jurisdiction"]["FDA"] == 1


class TestImportBatch:
    def test_create_and_update_batch(self, tmp_db):
        batch_id = tmp_db.create_import_batch("/source/path")
        assert batch_id is not None
        assert batch_id > 0

        tmp_db.update_import_batch(
            batch_id,
            total_files=10,
            imported=8,
            duplicates=1,
            errors=1,
            status="completed",
        )

        # Verify via direct query
        with tmp_db.connection() as conn:
            cursor = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,))
            batch = dict(cursor.fetchone())
            assert batch["total_files"] == 10
            assert batch["imported"] == 8
            assert batch["duplicates"] == 1
            assert batch["errors"] == 1
            assert batch["status"] == "completed"
            assert batch["completed_at"] is not None
