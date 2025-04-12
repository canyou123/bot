import g4f
def summarize_transcript_with_g4f(transcript, language="vi"):
    if language == "vi":
        prompt = f"phân tích chi tiết, dễ hiểu, ngắn gọn bằng tiếng việt:\n\n{transcript}"
    else:
        prompt = f"Summarize the following content in detail, make it easy to understand and concise:\n\n{transcript}"

    try:
        response = g4f.ChatCompletion.create(
            model="gpt-4o-mini",  # Or other available models like "gpt-4"
            messages=[{
                "role": "user",
                "content": prompt
            }])
        return response if response else "Lỗi: Không thể tóm tắt nội dung."
    except Exception as e:
        return f"Lỗi khi sử dụng GPT để tóm tắt: {str(e)}"
