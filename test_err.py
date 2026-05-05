import asyncio
import io
from parser import parse_file

async def test_invalid_docx():
    # Simulate invalid docx bytes
    invalid_data = b"This is not a zip file, so it cannot be a docx"
    file_name = "test.docx"
    
    questions, err = await parse_file(invalid_data, file_name)
    
    print(f"Error returned: {err}")
    if "Fayl o'qishda xatolik" in err or "Savollar topilmadi" in err:
        print("✅ Test passed: error handled gracefully.")
    else:
        print("❌ Test failed: error not handled as expected.")

if __name__ == "__main__":
    asyncio.run(test_invalid_docx())
