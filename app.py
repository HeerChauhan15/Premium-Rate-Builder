import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(
    page_title="Loader & GST Rate Calculator",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Loader & GST Rate Calculator")
st.caption("Enter a base rate manually, or upload an Age/Term rate sheet — GST and Loader are applied on top.")

GST_RATE_DEFAULT = 18.0

# ============================================
# FORMULA (same for both modes):
#   After Loader = Base Rate x (1 + Loader% / 100)
#   Final Rate   = After Loader x (1 + GST% / 100)
# ============================================
def apply_loader_and_gst(base_rate, loader_pct, gst_pct):
    after_loader = base_rate * (1 + (loader_pct / 100.0))
    final_rate = after_loader * (1 + (gst_pct / 100.0))
    return after_loader, final_rate


tab1, tab2 = st.tabs(["🖊 Manual Entry", "📁 Upload Rate Sheet"])

# ============================================
# TAB 1: MANUAL ENTRY
# ============================================
with tab1:
    st.subheader("Manual Rate Calculation")

    col1, col2, col3 = st.columns(3)
    with col1:
        base_rate = st.number_input(
            "Base Rate (per ₹1,00,000 Sum Assured)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.2f"
        )
    with col2:
        loader_pct = st.number_input(
            "Loader % (Header Loader)",
            min_value=0.0,
            max_value=500.0,
            value=0.0,
            step=1.0
        )
    with col3:
        gst_pct = st.number_input(
            "GST %",
            min_value=0.0,
            max_value=100.0,
            value=GST_RATE_DEFAULT,
            step=0.5
        )

    st.write("")
    if st.button("Calculate Final Rate", type="primary", use_container_width=True):
        if base_rate <= 0:
            st.error("Please enter a Base Rate greater than 0.")
        else:
            after_loader, final_rate = apply_loader_and_gst(base_rate, loader_pct, gst_pct)

            st.success(f"✅ Base {base_rate:,.2f} | Loader {loader_pct}% | GST {gst_pct}%")

            c1, c2, c3 = st.columns(3)
            c1.metric("Base Rate", f"{base_rate:,.2f}")
            c2.metric("After Loader", f"{after_loader:,.2f}")
            c3.metric("Final Rate (incl. GST)", f"{final_rate:,.2f}")

            st.caption(
                f"Formula used: Final Rate = Base × (1 + {loader_pct}/100) × (1 + {gst_pct}/100)"
            )

# ============================================
# TAB 2: UPLOAD RATE SHEET
# ============================================
with tab2:
    st.subheader("Full Rate Table from Uploaded Sheet")
    st.markdown(
        "Sheet must have an **AGE/TERM** style layout — a header row containing "
        "`AGE`, with tenure years as the remaining column headers."
    )

    st.markdown("**Step 1 — Set Loader % and GST % (required before upload is accepted)**")
    ec1, ec2 = st.columns(2)
    with ec1:
        excel_loader_pct = st.number_input(
            "Loader %",
            min_value=0.0,
            max_value=500.0,
            value=None,
            step=1.0,
            placeholder="Enter loader %",
            key="excel_loader"
        )
    with ec2:
        excel_gst_pct = st.number_input(
            "GST %",
            min_value=0.0,
            max_value=100.0,
            value=None,
            step=0.5,
            placeholder="Enter GST %",
            key="excel_gst"
        )

    loader_gst_ready = excel_loader_pct is not None and excel_gst_pct is not None

    if not loader_gst_ready:
        st.warning("⚠ Enter both Loader % and GST % above to unlock the file upload.")
    else:
        st.markdown("**Step 2 — Upload your rate sheet (.xlsx)**")
        uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx"])

        if uploaded_file is not None:
            try:
                raw = pd.read_excel(uploaded_file, sheet_name=0, header=None)

                header_row = None
                for i, row in raw.iterrows():
                    for val in row.values:
                        if isinstance(val, str) and "AGE" in val.upper():
                            header_row = i
                            break
                    if header_row is not None:
                        break

                if header_row is None:
                    raise ValueError("Could not find an AGE/TERM header row in the uploaded sheet.")

                uploaded_file.seek(0)
                df = pd.read_excel(uploaded_file, sheet_name=0, header=header_row)
                df.columns = [str(c).strip() for c in df.columns]

                age_col = df.columns[0]
                df = df.dropna(subset=[age_col])
                df[age_col] = pd.to_numeric(df[age_col], errors="coerce")
                df = df.dropna(subset=[age_col])
                df[age_col] = df[age_col].astype(int)
                df = df.set_index(age_col)

                tenure_cols = []
                for col in df.columns:
                    try:
                        int(float(col))
                        tenure_cols.append(col)
                    except Exception:
                        pass

                if not tenure_cols:
                    raise ValueError("No tenure/term columns found in the sheet.")

                result = df[tenure_cols].apply(
                    lambda s: pd.to_numeric(s, errors="coerce")
                )

                # Apply Loader then GST to every cell
                result = result * (1 + (excel_loader_pct / 100.0))
                result = result * (1 + (excel_gst_pct / 100.0))
                result = result.round(2)

                result = result.reset_index()
                result = result.rename(columns={age_col: "AGE/TERM"})

                st.success(
                    f"✅ Loaded table generated | Loader {excel_loader_pct}% | GST {excel_gst_pct}%"
                )
                st.dataframe(result, use_container_width=True)

                buffer = io.BytesIO()
                result.to_excel(buffer, index=False)
                buffer.seek(0)

                st.download_button(
                    label="⬇ Download Loaded Rate Table",
                    data=buffer,
                    file_name=f"loaded_rate_table_loader{excel_loader_pct}_gst{excel_gst_pct}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Error: {e}")
