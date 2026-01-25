"""
Regulatory Knowledge Base - Web Interface

A Streamlit-based web UI for managing and searching regulatory documents.
"""

import os
import sys
from pathlib import Path

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

from regkb.config import config
from regkb.database import Database
from regkb.importer import DocumentImporter
from regkb.search import SearchEngine
from regkb.extraction import TextExtractor

# Page configuration
st.set_page_config(
    page_title="Regulatory Knowledge Base",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize components (cached)
@st.cache_resource
def get_database():
    return Database()

@st.cache_resource
def get_search_engine():
    return SearchEngine()

@st.cache_resource
def get_importer():
    return DocumentImporter()

db = get_database()
search_engine = get_search_engine()
importer = get_importer()

# Custom CSS
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
    }
    .doc-card {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
        margin-bottom: 1rem;
    }
    .doc-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .doc-meta {
        color: #666;
        font-size: 0.9rem;
    }
    .score-badge {
        background-color: #28a745;
        color: white;
        padding: 0.2rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Sidebar navigation
    st.sidebar.title("📚 RegKB")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigation",
        ["🔍 Search", "📄 Browse", "➕ Add Document", "📊 Statistics", "⚙️ Settings"],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")

    # Quick stats in sidebar
    stats = db.get_statistics()
    st.sidebar.metric("Total Documents", stats["total_documents"])

    # Route to pages
    if page == "🔍 Search":
        search_page()
    elif page == "📄 Browse":
        browse_page()
    elif page == "➕ Add Document":
        add_document_page()
    elif page == "📊 Statistics":
        statistics_page()
    elif page == "⚙️ Settings":
        settings_page()


def search_page():
    st.title("🔍 Search Documents")

    # Search input
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Search query",
            placeholder="Enter your search (e.g., 'MDR clinical evaluation requirements')",
            label_visibility="collapsed"
        )
    with col2:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    # Filters
    with st.expander("🔧 Filters", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            doc_types = ["All"] + config.document_types
            selected_type = st.selectbox("Document Type", doc_types)
        with col2:
            jurisdictions = ["All"] + config.jurisdictions
            selected_jurisdiction = st.selectbox("Jurisdiction", jurisdictions)
        with col3:
            num_results = st.slider("Max Results", 5, 50, 10)

    # Perform search
    if query and (search_clicked or query):
        with st.spinner("Searching..."):
            try:
                results = search_engine.search(
                    query,
                    limit=num_results,
                    document_type=None if selected_type == "All" else selected_type,
                    jurisdiction=None if selected_jurisdiction == "All" else selected_jurisdiction,
                    include_excerpt=True
                )

                if results:
                    st.success(f"Found {len(results)} results")

                    for i, doc in enumerate(results, 1):
                        with st.container():
                            col1, col2 = st.columns([5, 1])

                            with col1:
                                st.markdown(f"**{i}. {doc['title']}**")
                                st.caption(f"📁 {doc['document_type']} | 🌍 {doc['jurisdiction']} | Score: {doc.get('relevance_score', 0):.3f}")

                                if doc.get('excerpt'):
                                    excerpt = doc['excerpt'][:300] + "..." if len(doc.get('excerpt', '')) > 300 else doc.get('excerpt', '')
                                    st.text(excerpt)

                            with col2:
                                if st.button("View", key=f"view_{doc['id']}"):
                                    st.session_state.selected_doc = doc['id']
                                    st.session_state.page = "detail"
                                    st.rerun()

                                file_path = Path(doc['file_path'])
                                if file_path.exists():
                                    with open(file_path, "rb") as f:
                                        st.download_button(
                                            "📥 PDF",
                                            f,
                                            file_name=file_path.name,
                                            mime="application/pdf",
                                            key=f"dl_{doc['id']}"
                                        )

                            st.markdown("---")
                else:
                    st.warning("No results found. Try different search terms.")

            except Exception as e:
                st.error(f"Search error: {e}")
    else:
        st.info("Enter a search query above to find documents.")

        # Show recent documents
        st.subheader("Recent Documents")
        recent = db.list_documents(limit=5)
        for doc in recent:
            st.markdown(f"- **{doc['title']}** ({doc['document_type']}, {doc['jurisdiction']})")


def browse_page():
    st.title("📄 Browse Documents")

    # Check if viewing a specific document
    if hasattr(st.session_state, 'selected_doc') and st.session_state.get('page') == 'detail':
        document_detail_view(st.session_state.selected_doc)
        if st.button("← Back to Browse"):
            st.session_state.page = "browse"
            st.rerun()
        return

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        doc_types = ["All"] + config.document_types
        filter_type = st.selectbox("Filter by Type", doc_types, key="browse_type")
    with col2:
        jurisdictions = ["All"] + config.jurisdictions
        filter_jurisdiction = st.selectbox("Filter by Jurisdiction", jurisdictions, key="browse_jur")
    with col3:
        per_page = st.selectbox("Documents per page", [10, 25, 50, 100], index=1)

    # Get documents
    documents = db.list_documents(
        document_type=None if filter_type == "All" else filter_type,
        jurisdiction=None if filter_jurisdiction == "All" else filter_jurisdiction,
        limit=per_page
    )

    if documents:
        # Create dataframe for display
        df = pd.DataFrame(documents)
        df = df[['id', 'title', 'document_type', 'jurisdiction', 'import_date']]
        df.columns = ['ID', 'Title', 'Type', 'Jurisdiction', 'Imported']

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "Title": st.column_config.TextColumn(width="large"),
                "Type": st.column_config.TextColumn(width="medium"),
                "Jurisdiction": st.column_config.TextColumn(width="medium"),
                "Imported": st.column_config.TextColumn(width="medium"),
            }
        )

        # Document selection
        st.markdown("---")
        doc_id = st.number_input("Enter Document ID to view details:", min_value=1, step=1)
        if st.button("View Document"):
            st.session_state.selected_doc = doc_id
            st.session_state.page = "detail"
            st.rerun()
    else:
        st.info("No documents found matching the filters.")


def document_detail_view(doc_id):
    doc = db.get_document(doc_id=doc_id)

    if not doc:
        st.error(f"Document {doc_id} not found.")
        return

    st.title(doc['title'])

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Document Information")

        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.markdown(f"**Type:** {doc['document_type']}")
            st.markdown(f"**Jurisdiction:** {doc['jurisdiction']}")
            st.markdown(f"**Version:** {doc.get('version') or 'N/A'}")
        with info_col2:
            st.markdown(f"**ID:** {doc['id']}")
            st.markdown(f"**Latest:** {'Yes' if doc.get('is_latest') else 'No'}")
            st.markdown(f"**Imported:** {doc['import_date'][:10]}")

        if doc.get('source_url'):
            st.markdown(f"**Source:** [{doc['source_url']}]({doc['source_url']})")

        if doc.get('description'):
            st.markdown(f"**Description:** {doc['description']}")

        # File path
        st.markdown(f"**File:** `{doc['file_path']}`")

        # Download button
        file_path = Path(doc['file_path'])
        if file_path.exists():
            with open(file_path, "rb") as f:
                st.download_button(
                    "📥 Download PDF",
                    f,
                    file_name=file_path.name,
                    mime="application/pdf"
                )

    with col2:
        st.subheader("Edit Metadata")

        with st.form("edit_form"):
            new_title = st.text_input("Title", value=doc['title'])
            new_type = st.selectbox(
                "Type",
                config.document_types,
                index=config.document_types.index(doc['document_type']) if doc['document_type'] in config.document_types else 0
            )
            new_jurisdiction = st.selectbox(
                "Jurisdiction",
                config.jurisdictions,
                index=config.jurisdictions.index(doc['jurisdiction']) if doc['jurisdiction'] in config.jurisdictions else 0
            )
            new_version = st.text_input("Version", value=doc.get('version') or '')
            new_description = st.text_area("Description", value=doc.get('description') or '')

            if st.form_submit_button("Save Changes"):
                updates = {
                    'title': new_title,
                    'document_type': new_type,
                    'jurisdiction': new_jurisdiction,
                    'version': new_version if new_version else None,
                    'description': new_description if new_description else None,
                }
                if db.update_document(doc_id, **updates):
                    st.success("Document updated!")
                    st.rerun()
                else:
                    st.error("Failed to update document.")

    # Extracted text preview
    if doc.get('extracted_path'):
        extracted_path = Path(doc['extracted_path'])
        if extracted_path.exists():
            st.subheader("Extracted Text Preview")
            with open(extracted_path, 'r', encoding='utf-8') as f:
                text = f.read()
            st.text_area("Content", text[:5000] + ("..." if len(text) > 5000 else ""), height=300, disabled=True)


def add_document_page():
    st.title("➕ Add Document")

    tab1, tab2, tab3 = st.tabs(["📁 Upload File", "🔗 From URL", "📂 Import Folder"])

    with tab1:
        st.subheader("Upload a PDF")

        uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])

        if uploaded_file:
            st.markdown("### Document Metadata")

            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Title", value=uploaded_file.name.replace('.pdf', '').replace('_', ' '))
                doc_type = st.selectbox("Document Type", config.document_types)
            with col2:
                jurisdiction = st.selectbox("Jurisdiction", config.jurisdictions)
                version = st.text_input("Version (optional)")

            source_url = st.text_input("Source URL (optional)")
            description = st.text_area("Description (optional)")

            if st.button("Add Document", type="primary"):
                with st.spinner("Processing document..."):
                    # Save uploaded file temporarily
                    temp_path = config.base_dir / "temp" / uploaded_file.name
                    temp_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(temp_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())

                    # Import
                    metadata = {
                        'title': title,
                        'document_type': doc_type,
                        'jurisdiction': jurisdiction,
                        'version': version if version else None,
                        'source_url': source_url if source_url else None,
                        'description': description if description else None,
                    }

                    doc_id = importer.import_file(temp_path, metadata)

                    # Cleanup
                    temp_path.unlink()

                    if doc_id:
                        st.success(f"Document added successfully! (ID: {doc_id})")
                        # Clear cache to refresh stats
                        st.cache_resource.clear()
                    else:
                        st.warning("Document already exists or import failed.")

    with tab2:
        st.subheader("Download from URL")

        url = st.text_input("Document URL", placeholder="https://example.com/document.pdf")

        if url:
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input("Title", key="url_title")
                doc_type = st.selectbox("Document Type", config.document_types, key="url_type")
            with col2:
                jurisdiction = st.selectbox("Jurisdiction", config.jurisdictions, key="url_jur")
                version = st.text_input("Version (optional)", key="url_version")

            description = st.text_area("Description (optional)", key="url_desc")

            if st.button("Download & Add", type="primary"):
                with st.spinner("Downloading and processing..."):
                    metadata = {
                        'title': title if title else None,
                        'document_type': doc_type,
                        'jurisdiction': jurisdiction,
                        'version': version if version else None,
                        'source_url': url,
                        'description': description if description else None,
                    }

                    doc_id = importer.import_from_url(url, metadata if title else None)

                    if doc_id:
                        st.success(f"Document added successfully! (ID: {doc_id})")
                        st.cache_resource.clear()
                    else:
                        st.error("Failed to download or document already exists.")

    with tab3:
        st.subheader("Import from Folder")

        folder_path = st.text_input("Folder Path", placeholder=r"C:\Documents\Regulatory")
        recursive = st.checkbox("Include subfolders", value=True)

        if folder_path and st.button("Start Import", type="primary"):
            folder = Path(folder_path)

            if not folder.exists():
                st.error("Folder does not exist.")
            else:
                with st.spinner("Importing documents..."):
                    result = importer.import_directory(folder, recursive=recursive, progress=False)

                    st.success(f"""
                    Import complete!
                    - **Imported:** {result.imported}
                    - **Duplicates skipped:** {result.duplicates}
                    - **Errors:** {result.errors}
                    """)

                    if result.error_details:
                        with st.expander("View Errors"):
                            for err in result.error_details:
                                st.text(f"{err['file']}: {err['error']}")

                    st.cache_resource.clear()

                    # Prompt to reindex
                    if result.imported > 0:
                        st.info("New documents added. Consider reindexing for better search results.")
                        if st.button("Reindex Now"):
                            with st.spinner("Reindexing..."):
                                search_engine.reindex_all()
                                st.success("Reindex complete!")


def statistics_page():
    st.title("📊 Statistics")

    stats = db.get_statistics()

    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Documents", stats["total_documents"])
    col2.metric("Latest Versions", stats["latest_versions"])
    col3.metric("Document Types", len(stats.get("by_type", {})))
    col4.metric("Jurisdictions", len(stats.get("by_jurisdiction", {})))

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Documents by Type")
        if stats.get("by_type"):
            df_type = pd.DataFrame(
                list(stats["by_type"].items()),
                columns=["Type", "Count"]
            ).sort_values("Count", ascending=False)
            st.bar_chart(df_type.set_index("Type"))
        else:
            st.info("No data available")

    with col2:
        st.subheader("Documents by Jurisdiction")
        if stats.get("by_jurisdiction"):
            df_jur = pd.DataFrame(
                list(stats["by_jurisdiction"].items()),
                columns=["Jurisdiction", "Count"]
            ).sort_values("Count", ascending=False)
            st.bar_chart(df_jur.set_index("Jurisdiction"))
        else:
            st.info("No data available")


def settings_page():
    st.title("⚙️ Settings")

    st.subheader("Database Management")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Backup Database**")
        st.caption("Create a backup of the current database")
        if st.button("Create Backup"):
            with st.spinner("Creating backup..."):
                backup_path = db.backup()
                st.success(f"Backup created: {backup_path}")

    with col2:
        st.markdown("**Reindex Search**")
        st.caption("Rebuild the search index for all documents")
        if st.button("Reindex All"):
            with st.spinner("Reindexing... This may take a few minutes."):
                count = search_engine.reindex_all()
                st.success(f"Indexed {count} documents")

    with col3:
        st.markdown("**Clear Cache**")
        st.caption("Clear application cache")
        if st.button("Clear Cache"):
            st.cache_resource.clear()
            st.success("Cache cleared!")

    st.markdown("---")

    st.subheader("Paths")
    st.code(f"""
Base Directory: {config.base_dir}
Archive:        {config.archive_dir}
Extracted:      {config.extracted_dir}
Database:       {config.database_path}
Backups:        {config.backups_dir}
    """)

    st.markdown("---")

    st.subheader("Document Types")
    st.write(", ".join(config.document_types))

    st.subheader("Jurisdictions")
    st.write(", ".join(config.jurisdictions))


if __name__ == "__main__":
    main()
