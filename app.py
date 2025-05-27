import os
import time
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_session import Session
from mongo import responses_collection  # Now using the unified collection
from bson import ObjectId  # For converting session ID to ObjectId

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a secure key for production

# Configure server-side sessions (using the filesystem)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./flask_session_dir"
app.config["SESSION_PERMANENT"] = False
Session(app)

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def generate_unique_filename(original_filename):
    timestamp = int(time.time())
    name, ext = os.path.splitext(original_filename)
    unique_filename = f"{name}_{timestamp}{ext}"
    return unique_filename

def save_excel(dataframe, file_id, output_filename="Rated.xlsx"):
    save_path = os.path.join(UPLOAD_FOLDER, f"{os.path.splitext(file_id)[0]}_{output_filename}")
    dataframe.to_excel(save_path, index=False)
    session["files"][file_id]["saved_file"] = save_path
    print("File saved at:", save_path)

def ensure_files_dict():
    if "files" not in session:
        session["files"] = {}

@app.route("/")
def home():
    return redirect(url_for("register"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        registration_data = {
            "name": request.form.get("name"),
            "email": request.form.get("email"),
            "graduation_year": request.form.get("graduation_year"),
            "age": request.form.get("age"),
            "gender": request.form.get("gender"),
            "highest_education": request.form.get("highest_education"),
            "use_llms": request.form.get("use_llms"),
            "incorrect_example": request.form.get("incorrect_example"),
            # "applied_llms": request.form.get("applied_llms"),
            # "difficult_case": request.form.get("difficult_case"),
            # "difficult_case_other": request.form.get("difficult_case_other"),
            "llm_usage": request.form.get("llm_usage")
        }
        
        # Insert a new document containing registration data and save its _id in the session
        if responses_collection is not None:
            result = responses_collection.insert_one({"registration": registration_data})
            session["response_id"] = str(result.inserted_id)
            print("Registration info saved to MongoDB:", registration_data)
        else:
            print("Registration info received (MongoDB not configured):", registration_data)
        
        return redirect(url_for("upload"))
    return render_template("register.html")

# @app.route("/feedback", methods=["GET", "POST"])
# def feedback():
#     if request.method == "POST":
#         feedback_data = {
#             "usage_coursework": request.form.get("usage_coursework"),
#             "usage_activities": request.form.get("usage_activities"),
#             "comprehensibility": request.form.get("comprehensibility"),
#             "fluency_english": request.form.get("fluency_english"),
#             "coverage": request.form.get("coverage"),
#             "relevance_accuracy": request.form.get("relevance_accuracy"),
#             "query_completion": request.form.get("query_completion"),
#             "proactiveness": request.form.get("proactiveness"),
#             "ethical_compliance": request.form.get("ethical_compliance"),
#             "multilingual_capacity": request.form.get("multilingual_capacity")
#         }
#         # Update the existing document with feedback data
#         if responses_collection is not None and "response_id" in session:
#             responses_collection.update_one(
#                 {"_id": ObjectId(session["response_id"])},
#                 {"$set": {"feedback": feedback_data}}
#             )
#             print("Feedback saved to MongoDB:", feedback_data)
#         else:
#             print("Feedback received (MongoDB not configured):", feedback_data)
        
#         return redirect(url_for("upload"))
#     return render_template("feedback.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    ensure_files_dict()
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            unique_filename = generate_unique_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            file.save(filepath)
            # Save file details in session keyed by unique filename
            session["files"][unique_filename] = {"file_path": filepath}
            # Read file columns and store them
            df = pd.read_excel(filepath)
            session["files"][unique_filename]["columns"] = df.columns.tolist()
            print("Uploaded file columns:", session["files"][unique_filename]["columns"])
            # Redirect to select_columns route with file id as query parameter
            return redirect(url_for("select_columns", file=unique_filename))
    return render_template("upload.html")

@app.route("/select_columns", methods=["GET", "POST"])
def select_columns():
    file_id = request.args.get("file")
    if not file_id or file_id not in session.get("files", {}):
        return redirect(url_for("upload"))
    
    file_details = session["files"][file_id]
   
    all_columns = file_details.get("columns", [])
    # Now:
    #FILES Column: second column (index 2)
    # Code snippet +10 lines column: fourth column (index 4)
    # Code snippet -10 lines: fifth column (index 5)
    # Comment: first (index 1)
    rating_candidates = ["ChatGPT", "Llama", "Gemini", "DeepSeek"]

    
    if request.method == "POST":
        # Get the mapping from the form
        files_col = request.form.get("File_column")
        code_snippet_plus_col = request.form.get("Code_snippet_+10_lines_column")
        code_snippet_minus_col = request.form.get("Code_snippet_-10_lines_column")
        comment_col = request.form.get("comment_column")
        llm_columns = request.form.getlist("selected_llms")
        
        file_details["llm_columns"] = llm_columns
        print(llm_columns)
        # Build groups from the Excel file.
        # Group rows by the unique query value (assumes each row has the query already).
        df = pd.read_excel(file_details["file_path"])
        groups_dict = {}
        groups_order = []
        group_list=[]
        for i, row in df.iterrows():
            raw_file = row.get(files_col, "")
            file_val = raw_file if (pd.notna(raw_file) and str(raw_file).strip()) else None
            code_snippet_plus_val = row.get(code_snippet_plus_col, "")
            code_snippet_plus_val = code_snippet_plus_val if (pd.notna(code_snippet_plus_val) and str(code_snippet_plus_val).strip()) else None
            code_snippet_minus_val = row.get(code_snippet_minus_col, "")
            code_snippet_minus_val =  code_snippet_minus_val if (pd.notna(code_snippet_minus_val) and str(code_snippet_minus_val).strip()) else None
            comment_val = row.get(comment_col, "")
            comment_val = comment_val if (pd.notna(comment_val) and str(comment_val).strip()) else None
            comment_ChatGpt_val = row.get("Comments(ChatGPT)", "")
            comment_ChatGpt_val = comment_ChatGpt_val if (pd.notna(comment_ChatGpt_val) and str(comment_ChatGpt_val).strip()) else None
            comment_Llama_val = row.get("Comments(Llama)", "")
            comment_Llama_val = comment_Llama_val if (pd.notna(comment_Llama_val) and str(comment_Llama_val).strip()) else None
            comment_Gemini_val = row.get("Comments(Gemini)", "")
            comment_Gemini_val = comment_Gemini_val if (pd.notna(comment_Gemini_val) and str(comment_Gemini_val).strip()) else None
            comment_DeepSeek_val = row.get("Comments(DeepSeek)", "")
            comment_DeepSeek_val = comment_DeepSeek_val if (pd.notna(comment_DeepSeek_val) and str(comment_DeepSeek_val).strip()) else None
            
            #response_type_val = row.get(type_col, "")
            info_dict={}
            if file_val is None:
                continue
            if i not in groups_dict:
                info_dict["file"]= file_val
                #groups_order.append(file_val)
            if code_snippet_plus_val is not None:
                info_dict["code_snippet_plus"]= code_snippet_plus_val
            if code_snippet_minus_val is not None:
                info_dict["code_snippet_minus"]= code_snippet_minus_val
            if comment_val is not None:
                info_dict["comment"]= comment_val
            if comment_ChatGpt_val is not None:
                info_dict["ChatGPT"]= comment_ChatGpt_val
            if comment_Llama_val is not None:
                info_dict["Llama"]= comment_Llama_val
            if comment_Gemini_val is not None:
                info_dict["Gemini"]= comment_Gemini_val
            if comment_DeepSeek_val is not None:
                info_dict["DeepSeek"]= comment_DeepSeek_val    
            group_list.append(info_dict)    
            
        #groups = [groups_dict[q] for q in groups_order]
        file_details["groups"] = group_list
        # Initialize navigation indices.
        file_details["current_group_idx"] = 0
        file_details["current_response_idx"] = 0
        # # Initialize ratings: a parallel structure (list of groups with one dict per response).
        
        
        rate=[]
        for _ in group_list:
            ratings = []
            for llm in rating_candidates:
                for j in range(0,5):
                    ratings.append({str(llm) + "_" + str(j):"NONE"})
                ratings.append({str(llm)+"_overall_rating":""})    
                ratings.append({str(llm)+"_feedback":""})    
            rate.append(ratings)    
        file_details["ratings"] = rate    
        
            
        
        
        
        
        session.modified = True
        
        return redirect(url_for("rate", file=file_id,
                                file_col=files_col,
                                code_snippet_plus_col=code_snippet_plus_col,
                                code_snippet_minus_col=code_snippet_minus_col,
                                comment_col=comment_col
                                ))
    
    return render_template("select_columns.html",
                           all_columns=all_columns,
                           rating_candidates=rating_candidates)


@app.route("/rate", methods=["GET", "POST"])
def rate():
    file_id = request.args.get("file") or request.form.get("file")
    if not file_id or file_id not in session.get("files", {}):
        return redirect(url_for("upload"))
    
    file_details = session["files"][file_id]
    filepath = file_details.get("file_path")
    if not filepath or not os.path.exists(filepath):
        return "File not found. <a href='/upload'>Upload again</a>"
    
    # Get column mappings from GET or POST
    if request.method == "POST":
        file_col = request.form.get("file_col")
        code_snippet_plus_col = request.form.get("code_snippet_plus_col")
        code_snippet_minus_col = request.form.get("code_snippet_minus_col")
        comment_col = request.form.get("comment_col")
        
    file_col = request.args.get("file_col")
    code_snippet_plus_col = request.args.get("code_snippet_plus_col")
    code_snippet_minus_col = request.args.get("code_snippet_minus_col")
    comment_col = request.args.get("comment_col")
        
    
    groups = file_details.get("groups", [])
    if not groups:
        return "No groups found. <a href='/upload'>Upload again</a>"
    
    total_groups = len(groups)
    current_group_idx = file_details.get("current_group_idx", 0)
    current_group = groups[current_group_idx]
    

    # total_responses = len(current_group.get("responses", []))
    
    if request.method == "POST":
        action = request.form.get("action")
        # Save ratings for all responses in the current group (without review field)
        ratings = file_details.get("ratings", [])
        current_group_ratings = ratings[current_group_idx]

        for res in range(0,len(current_group_ratings)):  # each response is a dict
            for key in current_group_ratings[res].keys():
                current_group_ratings[res][key] = request.form.get(key)
        ratings[current_group_idx] = current_group_ratings
        file_details["ratings"] = ratings
        
        # Navigation: change current_group_idx
        if action == "prev":
            if current_group_idx > 0:
                current_group_idx -= 1
        elif action == "next":
            if current_group_idx < total_groups - 1:
                current_group_idx += 1
            else:
                #If on the last group, merge ratings with original DataFrame and save file.
                # df = pd.read_excel(filepath)
                # ratings_dict = {}
                # for g_idx, group in enumerate(groups):
                #     for r_idx, resp in enumerate(group["responses"]):
                #         row_index = resp["row_index"]
                #         ratings_dict[row_index] = file_details["ratings"][g_idx][r_idx]
                # for col in file_details.get("rating_columns", []):
                #     df[col] = df.index.map(lambda i: ratings_dict.get(i, {}).get(col))
                # Removed merging for "response_review" as it's no longer used.

                df = pd.read_excel(filepath)
                for row_idx, rating_list in enumerate(ratings):
                    for entry in rating_list:
                        for col_name, value in entry.items():
                            # Assign value to the corresponding cell
                            df.at[row_idx, col_name] = value

                # Save the updated DataFrame back to Excel
                df.to_excel(filepath, index=False)
                save_excel(df, file_id)
                return redirect(url_for("download_page", file=file_id))
        
        file_details["current_group_idx"] = current_group_idx
        session.modified = True
        return redirect(url_for("rate", file=file_id,
                                 file_col=file_col,
                                code_snippet_plus_col=code_snippet_plus_col,
                                code_snippet_minus_col=code_snippet_minus_col,
                                comment_col=comment_col))
    
    # Prepare current ratings for the current group if available
    ratings = file_details.get("ratings", [])
    #current_rating = ratings[current_group_idx] if ratings and len(ratings) > current_group_idx else [{} for _ in range(total_responses)]
    llm_question = ["q1", "q2", "q3", "q4", "q5"]
    return render_template("rate.html",
                           current_group=current_group,
                           current_group_idx=current_group_idx,
                           total_groups=total_groups,
                           rating_columns=file_details.get("rating_columns", []),
                           file_col=file_col,
                           code_snippet_plus_col=code_snippet_plus_col,
                            code_snippet_minus_col=code_snippet_minus_col,
                            comment_col=comment_col,
                           file_id=file_id,
                           llm_col=file_details["llm_columns"],
                           llm_question=llm_question)


@app.route("/download_page", methods=["GET", "POST"])
def download_page():
    file_id = request.args.get("file")
    if not file_id or file_id not in session.get("files", {}):
        return "No file available for download. <a href='/upload'>Upload again</a>"
    
    saved_file = session["files"][file_id].get("saved_file")
    if not saved_file or not os.path.exists(saved_file):
        return "No file available for download. <a href='/upload'>Upload again</a>"
    
    comment_submitted = False
    if request.method == "POST":
        comment = request.form.get("comment")
        # Update the same document with the general comment
        if comment and responses_collection is not None and "response_id" in session:
            responses_collection.update_one(
                {"_id": ObjectId(session["response_id"])},
                {"$set": {"general_comment": comment}}
            )
            comment_submitted = True
    
    return render_template("download.html", file_id=file_id, comment_submitted=comment_submitted)

@app.route("/download")
def download():
    file_id = request.args.get("file")
    if (file_id and file_id in session.get("files", {}) and 
        "saved_file" in session["files"][file_id] and 
        os.path.exists(session["files"][file_id]["saved_file"])):
        return send_file(session["files"][file_id]["saved_file"], as_attachment=True)
    return "File not found. <a href='/upload'>Upload again</a>"

@app.route("/starter_queries")
def starter_queries():
    return render_template("starter_queries.html")


if __name__ == "__main__":
    app.run(debug=True)