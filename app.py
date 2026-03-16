import os
import zipfile
import tempfile
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium


st.set_page_config(
    page_title="Web GIS Join App Ucas 2026 120237490",
    page_icon="🌍",
    layout="wide"
)


# -----------------------------
# CSS بسيط لتحسين الشكل
# -----------------------------
st.markdown("""
<style>
    .main {
        padding-top: 1rem;
    }

    [data-testid="stSidebar"] {
        min-width: 360px;
        max-width: 360px;
    }

    .main-title {
        background: linear-gradient(90deg, #0f172a, #1e3a8a);
        padding: 18px;
        border-radius: 14px;
        color: white;
        text-align: center;
        margin-bottom: 12px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.15);
    }

    .sub-note {
        text-align: center;
        color: #cbd5e1;
        margin-bottom: 18px;
    }

    .section-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 14px;
    }

    .upload-box {
        background: linear-gradient(180deg, rgba(16,185,129,0.10), rgba(59,130,246,0.08));
        border: 1px dashed rgba(148,163,184,0.45);
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 10px;
    }

    .small-title {
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .soft-text {
        color: #cbd5e1;
        font-size: 14px;
    }

    .result-box {
        background: linear-gradient(180deg, rgba(30,41,59,0.70), rgba(15,23,42,0.85));
        border-radius: 14px;
        padding: 14px;
        border: 1px solid rgba(148,163,184,0.15);
        margin-top: 12px;
    }

    .metric-chip {
        display: inline-block;
        padding: 8px 14px;
        border-radius: 999px;
        background: rgba(16,185,129,0.12);
        border: 1px solid rgba(16,185,129,0.25);
        margin-bottom: 12px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Session State
# -----------------------------
if "result_gdf" not in st.session_state:
    st.session_state.result_gdf = None

if "result_message" not in st.session_state:
    st.session_state.result_message = ""

if "result_type" not in st.session_state:
    st.session_state.result_type = ""


# -----------------------------
# دالة تجهيز الجدول للعرض
# -----------------------------
def prepare_table_for_display(gdf, rows=5):
    table_df = gdf.head(rows).copy()

    for col in table_df.columns:
        if col == "geometry":
            table_df[col] = table_df[col].astype(str)
        elif table_df[col].dtype == "object":
            table_df[col] = table_df[col].astype(str)

    return table_df


# -----------------------------
# قراءة الطبقة
# -----------------------------
def read_layer(uploaded_file, layer_label):
    file_name = uploaded_file.name.lower()

    try:
        temp_dir = tempfile.mkdtemp()

        if file_name.endswith(".zip"):
            zip_path = os.path.join(temp_dir, uploaded_file.name)

            with open(zip_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            extract_dir = os.path.join(temp_dir, "unzipped")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            shp_path = None
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.lower().endswith(".shp"):
                        shp_path = os.path.join(root, file)
                        break
                if shp_path is not None:
                    break

            if shp_path is None:
                raise ValueError(f"الملف {layer_label} لا يحتوي على shapefile صالح داخل ZIP")

            gdf = gpd.read_file(shp_path)

        elif file_name.endswith(".geojson") or file_name.endswith(".json"):
            json_path = os.path.join(temp_dir, uploaded_file.name)

            with open(json_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            gdf = gpd.read_file(json_path)

        else:
            raise ValueError(f"صيغة الملف {layer_label} غير مدعومة. ارفع ZIP أو GeoJSON أو JSON فقط")

        if gdf.empty:
            raise ValueError(f"الملف {layer_label} تم قراءته لكنه فارغ")

        if "geometry" not in gdf.columns:
            raise ValueError(f"الملف {layer_label} لا يحتوي على عمود geometry")

        gdf = gdf[gdf.geometry.notnull()].copy()

        if gdf.empty:
            raise ValueError(f"الملف {layer_label} لا يحتوي على عناصر مكانية صالحة")

        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326, allow_override=True)

        return gdf

    except Exception as e:
        raise ValueError(f"حدث خطأ أثناء قراءة الملف {layer_label}: {str(e)}")


# -----------------------------
# توحيد CRS
# -----------------------------
def align_crs(left_gdf, right_gdf):
    if left_gdf.crs != right_gdf.crs:
        right_gdf = right_gdf.to_crs(left_gdf.crs)
    return left_gdf, right_gdf


# -----------------------------
# رسم الخريطة
# -----------------------------
def make_map(gdf, color="blue"):
    gdf_map = gdf.to_crs(epsg=4326)

    bounds = gdf_map.total_bounds
    center_x = (bounds[0] + bounds[2]) / 2
    center_y = (bounds[1] + bounds[3]) / 2

    m = folium.Map(location=[center_y, center_x], zoom_start=11)

    folium.GeoJson(
        gdf_map,
        style_function=lambda x: {
            "color": color,
            "weight": 2,
            "fillOpacity": 0.25
        }
    ).add_to(m)

    return m


# -----------------------------
# الربط المكاني
# -----------------------------
def run_spatial_join(left_gdf, right_gdf, relation, how_type):
    left_gdf, right_gdf = align_crs(left_gdf, right_gdf)

    result = gpd.sjoin(
        left_gdf,
        right_gdf,
        how=how_type,
        predicate=relation,
        lsuffix="left",
        rsuffix="right"
    )

    return result


# -----------------------------
# الربط الوصفي
# -----------------------------
def run_attribute_join(left_gdf, right_gdf, left_field, right_field, how_type):
    left_copy = left_gdf.copy()
    right_copy = right_gdf.copy()

    left_copy[left_field] = left_copy[left_field].astype(str)
    right_copy[right_field] = right_copy[right_field].astype(str)

    right_no_geom = right_copy.drop(columns="geometry", errors="ignore")

    result = pd.merge(
        left_copy,
        right_no_geom,
        left_on=left_field,
        right_on=right_field,
        how=how_type,
        suffixes=("_left", "_right")
    )

    result = gpd.GeoDataFrame(result, geometry="geometry", crs=left_gdf.crs)
    return result


# -----------------------------
# تجهيز GeoJSON للتنزيل
# -----------------------------
def result_to_geojson_bytes(result_gdf):
    temp_dir = tempfile.mkdtemp()
    out_path = os.path.join(temp_dir, "join_result.geojson")
    result_gdf.to_file(out_path, driver="GeoJSON")

    with open(out_path, "rb") as f:
        data = f.read()

    return data


# -----------------------------
# العنوان
# -----------------------------
st.markdown("""
<div class="main-title">
    <h1 style="margin:0;">تطبيق Web GIS للربط المكاني والربط الوصفي</h1>
</div>
<div class="sub-note">
    ارفع ملفين جغرافيين ثم اختر نوع الربط واعرض النتيجة ونزّلها بصيغة GeoJSON
</div>
""", unsafe_allow_html=True)


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("لوحة التحكم")
    st.write("1. ارفع الطبقة الأساسية")
    st.write("2. ارفع الطبقة الثانوية")
    st.write("3. اختر نوع الربط")
    st.write("4. نفذ العملية")
    st.write("5. نزّل النتيجة")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="upload-box">', unsafe_allow_html=True)
    st.markdown('<div class="small-title">رفع الطبقة الأساسية</div>', unsafe_allow_html=True)
    st.markdown('<div class="soft-text">يدعم ZIP Shapefile أو GeoJSON أو JSON</div>', unsafe_allow_html=True)

    left_file = st.file_uploader(
        "اختر ملف الطبقة الأساسية Left",
        type=["zip", "geojson", "json"],
        key="left_file",
        label_visibility="collapsed"
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="upload-box">', unsafe_allow_html=True)
    st.markdown('<div class="small-title">رفع الطبقة الثانوية</div>', unsafe_allow_html=True)
    st.markdown('<div class="soft-text">يدعم ZIP Shapefile أو GeoJSON أو JSON</div>', unsafe_allow_html=True)

    right_file = st.file_uploader(
        "اختر ملف الطبقة الثانوية Right",
        type=["zip", "geojson", "json"],
        key="right_file",
        label_visibility="collapsed"
    )
    st.markdown("</div>", unsafe_allow_html=True)


left_gdf = None
right_gdf = None

col1, col2 = st.columns(2)

# -----------------------------
# قراءة الطبقة الأولى
# -----------------------------
if left_file is not None:
    try:
        with st.spinner("جاري قراءة الطبقة الأساسية..."):
            left_gdf = read_layer(left_file, "Left")
        st.success("تم رفع الطبقة الأساسية بنجاح")
    except Exception as e:
        st.error(str(e))

# -----------------------------
# قراءة الطبقة الثانية
# -----------------------------
if right_file is not None:
    try:
        with st.spinner("جاري قراءة الطبقة الثانوية..."):
            right_gdf = read_layer(right_file, "Right")
        st.success("تم رفع الطبقة الثانوية بنجاح")
    except Exception as e:
        st.error(str(e))


# -----------------------------
# عرض الطبقة الأولى
# -----------------------------
if left_gdf is not None:
    with col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("الطبقة الأساسية Left")
        st.write("أول 5 صفوف")
        st.dataframe(prepare_table_for_display(left_gdf, 5), use_container_width=True)
        st.write("عدد السجلات:", len(left_gdf))
        st.write("الحقول:", list(left_gdf.columns))
        st.write("CRS:", left_gdf.crs)

        left_map = make_map(left_gdf, color="blue")
        st_folium(left_map, width=650, height=380)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# عرض الطبقة الثانية
# -----------------------------
if right_gdf is not None:
    with col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("الطبقة الثانوية Right")
        st.write("أول 5 صفوف")
        st.dataframe(prepare_table_for_display(right_gdf, 5), use_container_width=True)
        st.write("عدد السجلات:", len(right_gdf))
        st.write("الحقول:", list(right_gdf.columns))
        st.write("CRS:", right_gdf.crs)

        right_map = make_map(right_gdf, color="green")
        st_folium(right_map, width=650, height=380)
        st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# خيارات الربط
# -----------------------------
if left_gdf is not None and right_gdf is not None:
    st.markdown("---")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("اختيار نوع الربط")

    join_mode = st.radio(
        "اختر نوع العملية",
        ["Spatial Join", "Attribute Join"],
        horizontal=True
    )

    if join_mode == "Spatial Join":
        relation = st.selectbox(
            "اختر العلاقة المكانية",
            ["intersects", "within", "contains"]
        )

        how_type = st.selectbox(
            "اختر نوع الربط المكاني",
            ["left", "right", "inner"]
        )

        if st.button("تنفيذ الربط المكاني", use_container_width=True):
            try:
                with st.spinner("جاري تنفيذ الربط المكاني..."):
                    result_gdf = run_spatial_join(left_gdf, right_gdf, relation, how_type)

                st.session_state.result_gdf = result_gdf
                st.session_state.result_type = "spatial"

                if result_gdf.empty:
                    st.session_state.result_message = "لا توجد نتائج مطابقة"
                else:
                    st.session_state.result_message = "تم تنفيذ الربط المكاني بنجاح"

            except Exception as e:
                st.session_state.result_gdf = None
                st.session_state.result_message = f"خطأ في الربط المكاني: {str(e)}"

    else:
        left_fields = [col for col in left_gdf.columns if col != "geometry"]
        right_fields = [col for col in right_gdf.columns if col != "geometry"]

        left_field = st.selectbox("اختر حقل الربط من الطبقة الأولى", left_fields)
        right_field = st.selectbox("اختر حقل الربط من الطبقة الثانية", right_fields)

        how_type = st.selectbox(
            "اختر نوع الربط الوصفي",
            ["left", "right", "inner", "outer"]
        )

        if st.button("تنفيذ الربط الوصفي", use_container_width=True):
            try:
                with st.spinner("جاري تنفيذ الربط الوصفي..."):
                    result_gdf = run_attribute_join(
                        left_gdf,
                        right_gdf,
                        left_field,
                        right_field,
                        how_type
                    )

                st.session_state.result_gdf = result_gdf
                st.session_state.result_type = "attribute"

                if result_gdf.empty:
                    st.session_state.result_message = "لا توجد نتائج مطابقة"
                else:
                    st.session_state.result_message = "تم تنفيذ الربط الوصفي بنجاح"

            except Exception as e:
                st.session_state.result_gdf = None
                st.session_state.result_message = f"خطأ في الربط الوصفي: {str(e)}"

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# عرض الرسائل
# -----------------------------
if st.session_state.result_message:
    if "خطأ" in st.session_state.result_message:
        st.error(st.session_state.result_message)
    elif "لا توجد" in st.session_state.result_message:
        st.warning(st.session_state.result_message)
    else:
        st.success(st.session_state.result_message)


# -----------------------------
# عرض النتيجة
# -----------------------------
if st.session_state.result_gdf is not None:
    result_gdf = st.session_state.result_gdf

    st.markdown("---")
    st.markdown('<div class="result-box">', unsafe_allow_html=True)
    st.subheader("النتيجة النهائية")
    st.markdown(
        f'<div class="metric-chip">عدد السجلات الناتجة: {len(result_gdf)}</div>',
        unsafe_allow_html=True
    )

    st.dataframe(prepare_table_for_display(result_gdf, 20), use_container_width=True)

    try:
        result_map = make_map(result_gdf, color="red")
        st_folium(result_map, width=1100, height=480)
    except Exception:
        st.info("تعذر عرض خريطة النتيجة لكن البيانات موجودة")

    try:
        geojson_data = result_to_geojson_bytes(result_gdf)

        c1, c2 = st.columns([3, 1])

        with c1:
            st.download_button(
                label="تنزيل النتيجة بصيغة GeoJSON",
                data=geojson_data,
                file_name="join_result.geojson",
                mime="application/geo+json",
                use_container_width=True
            )

        with c2:
            if st.button("مسح النتيجة", use_container_width=True):
                st.session_state.result_gdf = None
                st.session_state.result_message = ""
                st.session_state.result_type = ""
                st.rerun()

    except Exception as e:
        st.error(f"تعذر تجهيز ملف التنزيل: {str(e)}")

    st.markdown("</div>", unsafe_allow_html=True)
