from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import io
import os
import uuid
from datetime import datetime

app = FastAPI(title="GST Reco Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
REPORT_DIR = "reports"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

@app.get("/")
def home():
    return {"message": "GST Reconciliation Pro is running!"}

@app.post("/upload")
async def upload_files(
    books_file: UploadFile = File(...),
    portal_file: UploadFile = File(...)
):
    try:
        # Generate unique ID for this job
        job_id = str(uuid.uuid4())[:8]
        
        # Read books file
        books_content = await books_file.read()
        if books_file.filename.endswith(('.xlsx', '.xls')):
            books_df = pd.read_excel(io.BytesIO(books_content))
        else:
            books_df = pd.read_csv(io.BytesIO(books_content))
        
        # Read portal file
        portal_content = await portal_file.read()
        if portal_file.filename.endswith(('.xlsx', '.xls')):
            portal_df = pd.read_excel(io.BytesIO(portal_content))
        else:
            portal_df = pd.read_csv(io.BytesIO(portal_content))
        
        # Simple reconciliation logic
        merged = pd.merge(
            books_df, portal_df,
            on=['GSTIN', 'InvoiceNo', 'TotalAmount'],
            how='outer',
            indicator=True
        )
        
        exact_matches = len(merged[merged['_merge'] == 'both'])
        only_in_books = len(merged[merged['_merge'] == 'left_only'])
        only_in_portal = len(merged[merged['_merge'] == 'right_only'])
        
        # Save report
        report_filename = f"report_{job_id}.xlsx"
        report_path = os.path.join(REPORT_DIR, report_filename)
        
        with pd.ExcelWriter(report_path) as writer:
            merged.to_excel(writer, sheet_name='Reconciliation', index=False)
            books_df.to_excel(writer, sheet_name='Books Data', index=False)
            portal_df.to_excel(writer, sheet_name='Portal Data', index=False)
        
        return {
            "success": True,
            "job_id": job_id,
            "stats": {
                "books_records": len(books_df),
                "portal_records": len(portal_df),
                "exact_matches": exact_matches,
                "only_in_books": only_in_books,
                "only_in_portal": only_in_portal
            },
            "download_url": f"/download/{job_id}"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/download/{job_id}")
def download_report(job_id: str):
    report_path = os.path.join(REPORT_DIR, f"report_{job_id}.xlsx")
    if os.path.exists(report_path):
        return FileResponse(
            report_path,
            filename=f"GST_Report_{job_id}.xlsx",
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return {"error": "Report not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))