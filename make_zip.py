import os
import zipfile

def create_submission_zip():
    # The exact folders required by the competition
    folders_to_zip = ['output', 'source', 'demo']
    
    with zipfile.ZipFile('submission.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for folder in folders_to_zip:
            if os.path.exists(folder):
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Add to zip with the exact required folder structure
                        zipf.write(file_path, arcname=file_path)
                        
    print("Success! submission.zip created.")
    print(f"File size: {os.path.getsize('submission.zip') / (1024*1024):.2f} MB")

if __name__ == "__main__":
    create_submission_zip()