import streamlit as st
import cv2
import os
import img2pdf
import shutil
import numpy as np
import tempfile

# 画面のレイアウトを横広（ワイド）に設定
st.set_page_config(page_title="Video to PDF Slide Extractor", layout="wide")

st.title("🎬 講義動画スライド 高精度PDF抽出ツール (Web App版)")
st.write("動画内のスライド変化を自動検出し、ブラウザ上で目視確認してPDF化します。")

# ---------------------------------------------------------
# サイドバー：設定エリア（元のコードの▼▼ 設定エリア ▼▼をUI化）
# ---------------------------------------------------------
st.sidebar.header("⚙️ パラメータ設定")
THRESHOLD = st.sidebar.slider("感度 THRESHOLD (小さいほど敏感)", 0.1, 5.0, 1.0, 0.1)
CHECK_INTERVAL = st.sidebar.number_input("チェック間隔 CHECK_INTERVAL (フレーム数)", min_value=1, value=13)

if st.sidebar.button("🔄 データをクリアして最初からやり直す"):
    if "extracted_images" in st.session_state:
        del st.session_state.extracted_images
    st.rerun()

# ---------------------------------------------------------
# STEP 1: 動画のアップロード ＆ 画像抽出
# ---------------------------------------------------------
uploaded_file = st.file_uploader("講義動画（.mp4）をアップロードしてください", type=["mp4"])

if uploaded_file:
    # アップロードされたバイナリデータを、OpenCVが読み込めるように一時ファイルとしてローカルに保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
        tfile.write(uploaded_file.read())
        video_path = tfile.name

    # Streamlit特有の再実行による「無限処理ループ」を防ぐため、セッション状態に保存
    if "extracted_images" not in st.session_state:
        st.info("■ STEP 1: 動画からスライドの変化を抽出しています。しばらくお待ちください...")
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        prev_frame_gray = None
        slide_count = 0
        frame_count = 0
        
        # 一時的な保存ディレクトリ（work_images）
        output_dir = "work_images"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)
        
        # Web画面用の進捗バーをデプロイ
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        extracted_paths = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % CHECK_INTERVAL == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                is_new_slide = False
                
                if prev_frame_gray is None:
                    is_new_slide = True
                else:
                    # ★ Saikaくんの「差分検知ロジック」をそのまま実行
                    diff = cv2.absdiff(prev_frame_gray, gray)
                    if np.mean(diff) > THRESHOLD:
                        is_new_slide = True

                if is_new_slide:
                    filename = os.path.join(output_dir, f"slide_{slide_count:04d}.jpg")
                    cv2.imwrite(filename, frame)
                    extracted_paths.append(filename)
                    prev_frame_gray = gray
                    slide_count += 1

            # 進捗バーの更新（負荷軽減のため、一定フレームごとに更新）
            if total_frames > 0 and frame_count % max(1, (total_frames // 20)) == 0:
                progress = frame_count / total_frames
                progress_bar.progress(min(1.0, progress))
                status_text.text(f"進捗: {int(progress * 100)}% ... ({slide_count}枚 抽出完了)")

            frame_count += 1
            
        cap.release()
        try:
            os.unlink(video_path)  # 使い終わった一時動画ファイルをクリーンアップ
        except:
            pass
        
        # 抽出結果を記憶
        st.session_state.extracted_images = extracted_paths
        st.success(f"🎉 抽出完了！ {len(extracted_paths)}枚のスライド候補が見つかりました。")

    # ---------------------------------------------------------
    # STEP 2: 一時停止 ＆ 手作業タイム (Web UIによる目視チェック)
    # ---------------------------------------------------------
    if "extracted_images" in st.session_state and st.session_state.extracted_images:
        st.markdown("---")
        st.subheader("📸 STEP 2: 不要な画像の除外 (手作業タイム)")
        st.write("抽出されたスライドが並んでいます。不要な画像（顔のアップなど）のチェックを外してください。")
        
        selected_images = []
        # 画面を4列の綺麗なグリッド状に分割して並べる（洗練されたUX）
        cols = st.columns(4)
        
        for i, img_path in enumerate(st.session_state.extracted_images):
            if os.path.exists(img_path):
                with cols[i % 4]:
                    # 枠の中に画像を表示
                    st.image(img_path, use_container_width=True)
                    # 各画像の下に個別のチェックボックスを配置（デフォルトはチェックON＝残す）
                    keep = st.checkbox(f"スライド {i+1} を含める", value=True, key=f"keep_{i}")
                    if keep:
                        selected_images.append(img_path)

        # ---------------------------------------------------------
        # STEP 3: PDF結合 ➔ ダウンロード
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader("📄 STEP 3: PDFの生成と保存")
        
        if st.button("🚀 選択したスライドでPDFを構築する"):
            if selected_images:
                try:
                    selected_images.sort()
                    # メモリ上でPDFを即時生成（コンパイル）
                    pdf_data = img2pdf.convert(selected_images)
                    
                    # ブラウザへのダウンロードボタンを有効化！
                    st.download_button(
                        label="📥 完成したPDFをダウンロード",
                        data=pdf_data,
                        file_name="lecture_complete.pdf",
                        mime="application/pdf"
                    )
                    st.success("ALL GREEN！PDFのビルドに成功しました。上のボタンを押して保存してください！")
                except Exception as e:
                    st.error(f"PDF作成エラー: {e}")
            else:
                st.error("エラー: 画像が1枚も選択されていません。最低1枚はチェックを残してください。")