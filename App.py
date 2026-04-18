from flask import Flask, render_template, request, session, flash, url_for, redirect, Response, make_response
import logging
import mysql.connector
import sys, fsdk, math, ctypes, time
import io
import datetime # Correctly imported now!
import csv
import re
from werkzeug.security import generate_password_hash, check_password_hash # Consolidated and correct
from io import StringIO

app = Flask(__name__)
app.secret_key = 'aaa'
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ... rest of your App.py code ...
STUDENT_TABLE_COLUMNS = {
    'Registerno': 'Registerno',
    'Name': 'Name',
    'Department': 'Department',
    'Batch': 'Batch',
    'Year': 'Year'
}
# Example helper for database connection (recommended, but you can stick to direct connect for now)
def get_db_connection():
    """Helper function to get a database connection."""
    try:
        conn = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='1faceattandanceinoutdb',
            charset='utf8'
        )
        return conn
    except mysql.connector.Error as err:
        # In a real app, you might log this error instead of flashing to user directly
        flash(f"Database connection error: {err}", "danger")
        return None


@app.route('/')
def home():
    return render_template('index.html')

# --- Login Pages ---
@app.route('/login_selection_page') # This line should have NO leading spaces
def login_selection_page():
    # You'll create this login_selection_page.html file if you haven't already
    return render_template('login_selection_page.html')

@app.route('/AdminLogin')
def AdminLogin():
    return render_template('AdminLogin.html')


@app.route('/NewFaculty')
def NewFaculty():
    return render_template('NewFaculty.html')

@app.route("/adminlogin", methods=['POST'])
def adminlogin():
    if request.form['uname'] == 'admin' and request.form['password'] == 'admin':
        flash("You are Logged In...!")
        return redirect(url_for('AdminHome'))
    else:
        flash("Username or Password is Wrong...!")
        return redirect(url_for('home'))

# --- Add this new route to your App.py ---
@app.route('/logout')
def logout():
    # Clear any session variables related to the user's login status
    session.pop('admin_logged_in', None) # If you set this during login
    session.pop('username', None)        # If you store the username in session

    flash("You have been logged out successfully.", 'info')
    return redirect(url_for('home')) # Redirect to your home page or login selection

# ... (your existing routes like DeleteFaculty, AStudentInfo, AAttendanceInfo, newfac) ...


@app.route("/AdminHome")
def AdminHome():
    conn = None
    cur = None
    data = []

    try:
        conn = get_db_connection()
        if conn:
            # Make sure dictionary=True is here and it's selecting from regtb
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, Name, Mobile, Email, subject, role, username, password FROM regtb") # Or just SELECT *
            data = cur.fetchall()

    except mysql.connector.Error as err:
        flash(f"Error fetching faculty details: {err}", "danger")
        print(f"Database error in AdminHome: {err}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template('AdminHome.html', data=data)


@app.route('/DeleteFaculty', methods=['POST'])
def delete_faculty():
    username = request.form.get('username') # Use .get() for safer access, returns None if not found
    conn = None
    cursor = None

    if not username:
        flash('No username provided for deletion.', 'danger')
        return redirect(url_for('AdminHome'))

    try:
        # Use your consistent get_db_connection function
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Could not delete faculty.", "danger")
            return redirect(url_for('AdminHome'))

        cursor = conn.cursor() # No need for dictionary=True here as we're just deleting

        # Execute DELETE query on 'regtb' as per your requirement
        cursor.execute("DELETE FROM regtb WHERE username = %s", (username,))
        conn.commit()

        if cursor.rowcount > 0: # Check if any row was actually deleted
            flash(f'Faculty member "{username}" removed successfully.', 'success')
        else:
            flash(f'Faculty member "{username}" not found or already removed.', 'info')

    except mysql.connector.Error as err:
        # Catch specific database errors
        flash(f'Database error removing faculty: {err}', 'danger')
        print(f"Database error in delete_faculty: {err}") # For server-side debugging
        if conn:
            conn.rollback() # Rollback changes if an error occurs

    except Exception as e:
        # Catch any other unexpected errors
        flash(f'An unexpected error occurred: {e}', 'danger')
        print(f"Unexpected error in delete_faculty: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Use url_for for better practice and maintainability
    return redirect(url_for('AdminHome'))

# --- Your AdminHome route would be here as well ---

@app.route("/AStudentInfo")
def AStudentInfo():

    conn = None
    cur = None
    students_data = []
    batches_data = []

    selected_batch = request.args.get('batch')

    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()

            # First, fetch all unique batches for the dropdown
            cur.execute("SELECT DISTINCT Batch FROM studenttb ORDER BY Batch DESC") # Using 'Batch' column for sorting batches
            batches_data = [row[0] for row in cur.fetchall()]

            # This is the correct column name from your DESCRIBE output
            CORRECT_REG_NO_COLUMN_NAME = 'RegisterNo' # <-- THIS IS THE CHANGE!

            # Then, fetch student data based on the selected batch
            if selected_batch and selected_batch != 'all':
                cur.execute(f"SELECT * FROM studenttb WHERE Batch = %s ORDER BY {CORRECT_REG_NO_COLUMN_NAME} ASC", (selected_batch,))
                students_data = cur.fetchall()
            elif selected_batch == 'all':
                cur.execute(f"SELECT * FROM studenttb ORDER BY {CORRECT_REG_NO_COLUMN_NAME} ASC")
                students_data = cur.fetchall()
            # If no batch is selected, students_data remains empty, which is a good default for large datasets

    except mysql.connector.Error as err:
        flash(f"Error fetching data: {err}", "danger")
        print(f"Database error in AStudentInfo: {err}") # For debugging
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        'AStudentInfo.html',
        students_data=students_data,
        batches_data=batches_data,
        selected_batch=selected_batch
    )

ATTENDANCE_TABLE_COLUMNS = {
    'Datetime': 'Datetime', # This is the actual column name in attentb
    'Attendance': 'Attendance',
    'Regno': 'Regno' # For the JOIN condition in attentb
}

def get_filtered_attendance_data(depart, batch, year, date_filter_str):
    conn = None
    cur = None
    processed_attendance_data = []

    try:
        conn = get_db_connection()
        if conn is None:
            print("DEBUG: get_filtered_attendance_data: No DB connection established.")
            return []

        cur = conn.cursor()

        query = f"""
            SELECT s.{STUDENT_TABLE_COLUMNS['Registerno']}, s.{STUDENT_TABLE_COLUMNS['Name']},
                   s.{STUDENT_TABLE_COLUMNS['Department']}, s.{STUDENT_TABLE_COLUMNS['Batch']}, s.{STUDENT_TABLE_COLUMNS['Year']},
                   a.{ATTENDANCE_TABLE_COLUMNS['Datetime']}, a.{ATTENDANCE_TABLE_COLUMNS['Attendance']}
            FROM studenttb s
            JOIN attentb a ON s.{STUDENT_TABLE_COLUMNS['Registerno']} = a.{ATTENDANCE_TABLE_COLUMNS['Regno']}
            WHERE 1=1
        """
        params = []

        if depart:
            query += f" AND s.{STUDENT_TABLE_COLUMNS['Department']} = %s"
            params.append(depart)
        if batch:
            query += f" AND s.{STUDENT_TABLE_COLUMNS['Batch']} = %s"
            params.append(batch)
        if year:
            query += f" AND s.{STUDENT_TABLE_COLUMNS['Year']} = %s"
            params.append(year)
        if date_filter_str:
            query += f" AND DATE(a.{ATTENDANCE_TABLE_COLUMNS['Datetime']}) = %s"
            params.append(date_filter_str)

        query += f" ORDER BY s.{STUDENT_TABLE_COLUMNS['Registerno']} ASC, a.{ATTENDANCE_TABLE_COLUMNS['Datetime']} DESC"

        print(f"\n--- ATTENDANCE DEBUG ---")
        print(f"Filter inputs: Department={depart}, Batch={batch}, Year={year}, Date={date_filter_str}")
        print(f"Constructed Query: {query}")
        print(f"Query Parameters: {params}")
        print(f"--- END ATTENDANCE DEBUG ---\n")

        cur.execute(query, tuple(params))
        fetched_data = cur.fetchall()

        datetime_col_index = 5

        for row in fetched_data:
            row_list = list(row)

            if isinstance(row_list[datetime_col_index], str):
                try:
                    row_list[datetime_col_index] = datetime.datetime.strptime(row_list[datetime_col_index], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        date_obj = datetime.datetime.strptime(row_list[datetime_col_index], '%Y-%m-%d').date()
                        row_list[datetime_col_index] = datetime.datetime.combine(date_obj, datetime.time.min)
                    except ValueError:
                        row_list[datetime_col_index] = None
            # THIS IS THE LINE THAT NEEDS THE CHANGE:
            elif isinstance(row_list[datetime_col_index], datetime.date) and not isinstance(row_list[datetime_col_index], datetime.datetime):
                row_list[datetime_col_index] = datetime.datetime.combine(row_list[datetime_col_index], datetime.time.min)

            processed_attendance_data.append(tuple(row_list))

    except mysql.connector.Error as err:
        print(f"Database error in get_filtered_attendance_data: {err}")
        processed_attendance_data = []
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return processed_attendance_data





@app.route("/AAttendanceInfo", methods=['GET', 'POST'])
def AAttendanceInfo():
    conn = None
    cur = None
    data = [] # This will hold the attendance records

    # Initialize request_form with default values for GET requests
    # For POST requests, these will be overwritten by form data
    request_form = {
        'depart': 'MCA', # Default Department to MCA
        'Batch': '',
        'year': 'I Year', # Default Year to I Year
        'date': datetime.date.today().isoformat(), # Default to today's date
        'shift': '' # Add shift to request_form
    }

    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return render_template('AAttendanceInfo.html', data=data, request_form=request_form)

        cur = conn.cursor(buffered=True, dictionary=True)

        if request.method == 'POST':
            # Retrieve filter criteria from the form
            depart = request.form.get('depart')
            batch = request.form.get('Batch')
            year = request.form.get('year')
            selected_date_str = request.form.get('date')
            shift = request.form.get('shift')

            # Update request_form with submitted values for display
            request_form['depart'] = depart
            request_form['Batch'] = batch
            request_form['year'] = year
            request_form['date'] = selected_date_str
            request_form['shift'] = shift

            # Validation: All fields including shift are required for search
            if not all([depart, batch, year, selected_date_str, shift]):
                flash("Please select Department, Batch, Year, Date, and Shift to filter records.", "warning")
            else:
                # Construct the base query
                query = """
                    SELECT Regno, Name, Department, Batch, Year, Datetime, Attendance, Shift
                    FROM attentb
                    WHERE 1=1
                """
                params = []

                if depart:
                    query += " AND Department = %s"
                    params.append(depart)
                if batch:
                    query += " AND Batch = %s"
                    params.append(batch)
                if year:
                    query += " AND Year = %s"
                    params.append(year)
                if selected_date_str:
                    query += " AND DATE(Datetime) = %s"
                    params.append(selected_date_str)
                if shift:
                    query += " AND Shift = %s"
                    params.append(shift)

                query += " ORDER BY Regno ASC, Datetime ASC"

                cur.execute(query, tuple(params))
                data = cur.fetchall()

                if not data:
                    flash("No attendance records found for the selected criteria.", "info")

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        print(f"Database error in AAttendanceInfo: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        print(f"Unexpected error in AAttendanceInfo: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template('AAttendanceInfo.html', data=data, request_form=request_form)


@app.route('/Adownload_attendance', methods=['POST'])
def Adownload_attendance():
    conn = None
    cur = None
    try:
        depart = request.form.get('depart')
        batch = request.form.get('Batch')
        year = request.form.get('year')
        date_filter = request.form.get('date')
        shift = request.form.get('shift')

        # Basic validation for download filters - all are required for a specific download
        if not all([depart, batch, year, date_filter, shift]):
            flash("Please select all filter criteria before attempting to download attendance.", "warning")
            return redirect(url_for('AAttendanceInfo'))

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Could not download CSV.", "danger")
            return redirect(url_for('AAttendanceInfo'))

        cur = conn.cursor(buffered=True, dictionary=True)

        query = """
            SELECT Regno, Name, Department, Batch, Year, Datetime, Attendance, Shift
            FROM attentb
            WHERE 1=1
        """
        params = []

        if depart:
            query += " AND Department = %s"
            params.append(depart)
        if batch:
            query += " AND Batch = %s"
            params.append(batch)
        if year:
            query += " AND Year = %s"
            params.append(year)
        if date_filter:
            query += " AND DATE(Datetime) = %s"
            params.append(date_filter)
        if shift:
            query += " AND Shift = %s"
            params.append(shift)

        cur.execute(query, tuple(params))
        records = cur.fetchall()

        if not records:
            flash("No attendance records found for download with the selected criteria.", "info")
            return redirect(url_for('AAttendanceInfo'))

        si = io.StringIO()
        cw = csv.writer(si)

        cw.writerow(['Register No', 'Name', 'Department', 'Batch', 'Year', 'Date & Time', 'Status', 'Shift'])

        for record in records:
            formatted_datetime = record['Datetime'].strftime('%Y-%m-%d %H:%M:%S') if record['Datetime'] else ''
            cw.writerow([
                record['Regno'],
                record['Name'],
                record['Department'],
                record['Batch'],
                record['Year'],
                formatted_datetime,
                record['Attendance'],
                record['Shift']
            ])

        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = f"attachment; filename=attendance_{depart}_{batch}_{year}_{date_filter}_{shift}_admin.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    except mysql.connector.Error as err:
        flash(f"Database error during CSV download: {err}", "danger")
        print(f"Database error in Adownload_attendance: {err}")
        return redirect(url_for('AAttendanceInfo'))
    except Exception as e:
        flash(f"An unexpected error occurred during CSV download: {e}", "danger")
        print(f"Unexpected error in Adownload_attendance: {e}")
        return redirect(url_for('AAttendanceInfo'))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/searchid")
def searchid():
    # eid= request.args.get('eid')
    # session['eid']=eid

    import LiveRecognition1  as liv1
    liv1.examvales()
    # liv1.att()
    # print(ExamName)


    return render_template('FacultyHome.html')

# --- Updated searchid1 route ---
@app.route("/searchid1")
def searchid1():
    recognition_status_message = ""
    try:
        import LiveRecognition2 as liv2 # Assuming LiveRecognition2.py exists and is similar
        recognition_status_message = liv2.examvales()
    except Exception as e:
        recognition_status_message = f"An error occurred while starting recognition: {e}"
        print(f"Error in /searchid1 route: {e}") # Print to your terminal for debugging

    flash(recognition_status_message, "info")
    return render_template('index.html')


def sendmsg(targetno,message):
    import requests
    requests.post(
        "http://sms.creativepoint.in/api/push.json?apikey=6555c521622c1&route=transsms&sender=FSSMSS&mobileno=" + targetno + "&text=Dear customer your msg is " + message + "  Sent By FSMSG FSSMSS")


# Assuming get_db_connection is defined as before
# from your_db_module import get_db_connection

@app.route("/newfac", methods=['GET', 'POST'])
def newfac():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        subject = request.form.get('subject')
        username = request.form.get('username')
        raw_password = request.form.get('password')

        errors = [] # List to collect validation errors

        # --- Server-Side Validation ---

        # Name: Keep it required, but no minlength or specific character checks as per request
        if not name or not name.strip():
            errors.append("Full Name is required.")

        # Mobile: Required and 10 digits
        if not mobile or not mobile.strip().isdigit() or len(mobile.strip()) != 10:
            errors.append("Mobile Number is required and must be exactly 10 digits.")

        # Email: Valid format required
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()):
            errors.append("Valid Email Address is required.")

        # Subject: Required and minimum 2 characters
        if not subject or len(subject.strip()) < 2:
            errors.append("Subject Taught is required and must be at least 2 characters.")

        # Username: Required and minimum 4 characters
        if not username or len(username.strip()) < 4:
            errors.append("Username is required and must be at least 4 characters.")

        # Password: Required, minimum 6 characters, at least one number, at least one special character
        if not raw_password or len(raw_password) < 6:
            errors.append("Password is required and must be at least 6 characters long.")
        if raw_password and not re.search(r"\d", raw_password): # At least one digit
            errors.append("Password must contain at least one number.")
        # At least one special character (adjust regex if you have a different set of special characters)
        if raw_password and not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", raw_password):
            errors.append("Password must contain at least one special character (e.g., !@#$%^&*).")


        # If any basic validation errors, flash them and re-render
        if errors:
            for error in errors:
                flash(error, "danger")
            # Keep the form data if validation fails, so user doesn't re-type everything
            return render_template('newfaculty.html',
                                   name=name, mobile=mobile, email=email,
                                   subject=subject, username=username) # Do NOT pass password back

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if conn is None:
                flash("Failed to connect to the database. Please try again later.", "danger")
                return render_template('newfaculty.html',
                                       name=name, mobile=mobile, email=email,
                                       subject=subject, username=username)

            cursor = conn.cursor()

            # Check for duplicate username or email
            cursor.execute("SELECT COUNT(*) FROM regtb WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone()[0] > 0:
                errors.append("Username or Email already exists. Please choose a different one.")
                for error in errors:
                    flash(error, "danger")
                return render_template('newfaculty.html',
                                       name=name, mobile=mobile, email=email,
                                       subject=subject, username=username)

            hashed_password = generate_password_hash(raw_password)
            role = 'faculty' # Define the role for new faculty

            sql_query = "INSERT INTO regtb (name, mobile, email, subject, username, password, role) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql_query, (name, mobile, email, subject, username, hashed_password, role))
            conn.commit()

            flash("Faculty registered successfully!", "success")
            return redirect(url_for('AdminHome'))

        except mysql.connector.Error as err:
            flash(f"Database error registering faculty: {err}", "danger")
            current_app.logger.error(f"Database error during faculty registration: {err}")
            if conn:
                conn.rollback() # Rollback changes if an error occurs

        except Exception as e:
            flash(f"An unexpected error occurred during registration: {e}", "danger")
            current_app.logger.error(f"Unexpected error in newfac POST: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # For GET requests or if POST fails and falls through
    return render_template('NewFaculty.html')


@app.route("/facultylogin", methods=['GET', 'POST'])
def facultylogin(): # This single function will handle both GET and POST requests
    if request.method == 'POST':
        # --- Handle the POST request (login form submission) ---
        username = request.form['username']
        raw_password = request.form['password'] # Get the password as entered by the user
        # --- ADD THESE PRINT STATEMENTS ---
        print(f"\n--- DEBUG: Faculty Login Attempt ---")
        print(f"Login attempt for username: '{username}'")
        print(f"Password entered by faculty: '{raw_password}'")
        # --- END ADDITIONS ---
        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(user='root', password='', host='localhost',
                                           database='1faceattandanceinoutdb', charset='utf8')
            cursor = conn.cursor()

            cursor.execute("SELECT username, password, email FROM regtb WHERE username = %s", (username,))
            data = cursor.fetchone()

            # --- ADD THESE PRINT STATEMENTS ---
            print(f"Data retrieved from DB for '{username}': {data}")
            if data:
                stored_hashed_password = data[1]
                print(f"Stored hashed password from DB: '{stored_hashed_password}'")
                password_match_result = check_password_hash(stored_hashed_password, raw_password)
                print(f"Result of check_password_hash: {password_match_result}")
            else:
                print(f"Username '{username}' not found in database.")
            print(f"------------------------------------\n")
            # --- END ADDITIONS ---

            if data and password_match_result:  # Use the variable for clarity
                # Login successful!
                session['loggedin'] = True
                session['username'] = username
                session['role'] = 'faculty'
                session['email'] = data[2]
                flash("You are successfully logged in!", "success")
                return redirect(url_for('FacultyHome'))
            else:
                flash("Incorrect Username or Password!", "danger")
                return render_template('FacultyLogin.html')

        except mysql.connector.Error as err:
            flash(f"Database error during login: {err}", "danger")
            print(f"Database error in /facultylogin (POST): {err}") # Log for debugging
            return render_template('FacultyLogin.html')
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
            print(f"Unexpected error in /facultylogin (POST): {e}") # Log for debugging
            return render_template('FacultyLogin.html')
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
    else:
        # --- Handle the GET request (display login form) ---
        # If it's a GET request, simply render the FacultyLogin.html page
        return render_template('FacultyLogin.html')


@app.route('/FacultyHome')
def FacultyHome():


    uname = session.get('username')
    conn = None
    cur = None
    faculty_data = []
    pending_leave_requests = []

    try:
        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8')
        cur = conn.cursor()

        # Fetch Faculty Data
        cur.execute("SELECT id, name, mobile, email, username FROM regtb WHERE username=%s", (uname,))
        faculty_data = cur.fetchall()

        # MODIFIED: Fetch ONLY PENDING Student Leave Requests WITH RegisterNo and Year
        cur.execute("""
            SELECT lr.id, lr.start_date, lr.end_date, lr.reason, lr.status, lr.request_date, s.name, s.RegisterNo, s.year
            FROM leave_requests lr
            INNER JOIN studenttb s ON lr.student_id = s.RegisterNo
            WHERE lr.status = 'Pending'
            ORDER BY lr.request_date DESC
        """)
        pending_leave_requests = cur.fetchall()

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        print(f"Database error in /FacultyHome: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        print(f"Unexpected error in /FacultyHome: {e}")
    finally:
        if cur:
            cur.close()
        if conn and conn.is_connected():
            conn.close()

    return render_template('FacultyHome.html', data=faculty_data, leave_requests=pending_leave_requests)


# --- MODIFIED: Faculty Leave History Page ---
@app.route('/FacultyLeaveHistory')
def faculty_leave_history():
    if not session.get('loggedin') or session.get('role') != 'faculty':
        flash("Please login as Faculty to access this page.", "danger")
        return redirect(url_for('facultylogin'))

    conn = None
    cur = None
    all_leave_requests = []

    try:
        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb',charset='utf8')
        cur = conn.cursor()

        # MODIFIED: Fetch ALL Student Leave Requests WITH RegisterNo and Year
        cur.execute("""
            SELECT lr.id, lr.start_date, lr.end_date, lr.reason, lr.status, lr.request_date, s.name, s.RegisterNo, s.year
            FROM leave_requests lr
            INNER JOIN studenttb s ON lr.student_id = s.RegisterNo
            ORDER BY lr.request_date DESC
        """)
        all_leave_requests = cur.fetchall()

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        print(f"Database error in /FacultyLeaveHistory: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        print(f"Unexpected error in /FacultyLeaveHistory: {e}")
    finally:
        if cur:
            cur.close()
        if conn and conn.is_connected():
            conn.close()

    return render_template('LeaveHistory.html', leave_requests=all_leave_requests)

# --- Your existing update_leave_status route (no changes needed here) ---
@app.route('/update_leave_status', methods=['POST'])
def update_leave_status():
    if not session.get('loggedin') or session.get('role') != 'faculty':
        flash("You need to log in as faculty to update leave status!", "danger")
        return redirect(url_for('facultylogin'))

    leave_request_id = request.form.get('leave_request_id')
    new_status = request.form.get('status')

    if not leave_request_id or not new_status:
        flash("Invalid request to update leave status!", "danger")
        return redirect(url_for('FacultyHome'))

    conn = None
    cur = None
    try:
        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8')
        cur = conn.cursor()

        cur.execute("""
            UPDATE leave_requests
            SET status = %s
            WHERE id = %s
        """, (new_status, leave_request_id))
        conn.commit()

        flash("Leave request status updated successfully!", "success")

    except Exception as e:
        flash(f"Error updating leave request status: {str(e)}", "danger")
        print(f"Error updating leave request status: {e}")

    finally:
        if cur:
            cur.close()
        if conn and conn.is_connected():
            conn.close()

    # After updating, redirect back to FacultyHome to show only remaining PENDING requests
    return redirect(url_for('FacultyHome'))



# --- NEW ROUTE FOR REMOVING STUDENT ---
@app.route("/remove_student", methods=['POST'])
def remove_student():
    # --- Security Check ---
    if 'loggedin' not in session or session.get('role') != 'faculty':
        flash("Please log in as a faculty member to perform this action.", "danger")
        return redirect(url_for('facultylogin'))

    registerno_to_delete = request.form.get('registerno')

    if not registerno_to_delete:
        flash("No student selected for removal.", "danger")
        return redirect(url_for('FStudentInfo')) # Redirect back to student info page

    conn = get_db_connection()
    cur = conn.cursor(buffered=True)
    try:
        # It's good practice to delete from related tables first if there are foreign key constraints
        # For this example, we'll assume no cascading deletes or handle them explicitly.
        # If attentb has a foreign key to studenttb on Registerno, you might need:
        # cur.execute("DELETE FROM attentb WHERE Regno = %s", (registerno_to_delete,))
        # cur.execute("DELETE FROM studenttb WHERE Registerno = %s", (registerno_to_delete,))

        # Assuming no foreign key issues or handled by DB settings (e.g., ON DELETE CASCADE)
        # Or if attentb stores all student details independently, you only need to delete from studenttb.
        # Given your attentb structure (with Name, Mobile, etc.), it suggests it might not strictly FK to studenttb.
        # If it doesn't, deleting from studenttb is sufficient for removing the student's primary record.

        # Delete from studenttb
        cur.execute("DELETE FROM studenttb WHERE Registerno = %s", (registerno_to_delete,))
        conn.commit()
        flash(f"Student with Register No. {registerno_to_delete} removed successfully.", "success")

    except mysql.connector.Error as err:
        flash(f"Database error during student removal: {err}", "danger")
        print(f"DB Error in remove_student: {err}")
        if conn:
            conn.rollback() # Rollback changes if an error occurs
    except Exception as e:
        flash(f"An unexpected error occurred during student removal: {e}", "danger")
        print(f"General Error in remove_student: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Redirect back to the student information page, potentially to the same batch filter
    return redirect(url_for('FStudentInfo', batch=request.form.get('current_batch_filter')))


# --- EXISTING FStudentInfo ROUTE (with minor adjustments) ---
@app.route("/FStudentInfo")
def FStudentInfo():


    conn = None
    cur = None
    students_data = []
    batches_data = []

    selected_batch = request.args.get('batch') # This comes from the dropdown selection

    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()

            # First, fetch all unique batches for the dropdown
            cur.execute("SELECT DISTINCT Batch FROM studenttb ORDER BY Batch DESC")
            batches_data = [row[0] for row in cur.fetchall()]

            # The column name 'Registerno' is used for sorting.
            # Make sure this matches your exact database column name (e.g., 'RegisterNo' vs 'Registerno').
            # Based on your prompt, 'RegisterNo' (camel case) was indicated, so let's stick to that for consistency.
            # However, your `INSERT` statements from previous discussions used `Registerno` (lowercase 'r').
            # It's critical that the column name used here matches your database's schema *exactly*.
            # For now, I'll use 'Registerno' as it appeared in your DB description.
            ORDER_BY_COLUMN = 'Registerno'

            # Then, fetch student data based on the selected batch
            if selected_batch and selected_batch != 'all':
                cur.execute(f"SELECT * FROM studenttb WHERE Batch = %s ORDER BY {ORDER_BY_COLUMN} ASC",
                            (selected_batch,))
                students_data = cur.fetchall()
            elif selected_batch == 'all':
                cur.execute(f"SELECT * FROM studenttb ORDER BY {ORDER_BY_COLUMN} ASC")
                students_data = cur.fetchall()
            else:
                # If no batch is explicitly selected (initial page load or 'Select a Batch' is chosen)
                # You might want to display all students by default, or no students.
                # Currently, it displays no students. If you want to show all by default,
                # you'd move the 'all' query here. For now, matching current behavior.
                pass

    except mysql.connector.Error as err:
        flash(f"Error fetching data: {err}", "danger")
        print(f"Database error in FStudentInfo: {err}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template(
        'FStudentInfo.html',
        students_data=students_data,
        batches_data=batches_data,
        selected_batch=selected_batch # Pass this to retain dropdown selection
    )


# --- Faculty Attendance Routes ---

# Assuming this route is present in your App.py
@app.route('/FAttendanceInfo', methods=['GET', 'POST'])
def FAttendanceInfo():
    conn = None
    cur = None
    data = [] # This will hold the attendance records
    # Initialize request_form with default values
    request_form = {
        'depart': request.form.get('depart', 'MCA'), # Default to MCA
        'Batch': request.form.get('Batch', ''),
        'year': request.form.get('year', ''),
        # --- THIS IS THE CRITICAL LINE ---
        'date': request.form.get('date', datetime.date.today().isoformat()),
        # --- END CRITICAL LINE ---
        'shift': request.form.get('shift', '') # Add shift to request_form
    }

    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return render_template('FAttendanceInfo.html', data=data, request_form=request_form)

        cur = conn.cursor(buffered=True, dictionary=True)

        if request.method == 'POST':
            # Retrieve filter criteria from the form
            depart = request.form.get('depart')
            batch = request.form.get('Batch')
            year = request.form.get('year')
            selected_date_str = request.form.get('date')  # <--- CORRECT WAY TO GET THE DATE FROM THE FORM
            shift = request.form.get('shift')  # Retrieve shift from form

            # Update request_form with submitted values for display
            request_form['depart'] = depart
            request_form['Batch'] = batch
            request_form['year'] = year
            request_form['date'] = selected_date_str  # Update request_form with the value received from the form
            request_form['shift'] = shift  # Store shift in request_form

            if not all([depart, batch, year, selected_date_str, shift]):  # All fields including shift are required
                flash("Please select Department, Batch, Year, Date, and Shift to filter records.", "warning")
            else:
                # ... (rest of your query building logic) ...
                # Construct the base query
                query = "SELECT Regno, Name, Department, Batch, Year, Datetime, Attendance, Shift FROM attentb WHERE 1=1"
                params = []

                if depart:
                    query += " AND Department = %s"
                    params.append(depart)
                if batch:
                    query += " AND Batch = %s"
                    params.append(batch)
                if year:
                    query += " AND Year = %s"
                    params.append(year)
                if selected_date_str:
                    query += " AND DATE(Datetime) = %s"
                    params.append(selected_date_str)
                if shift:  # Add shift to the query
                    query += " AND Shift = %s"
                    params.append(shift)

                query += " ORDER BY Regno ASC, Datetime ASC"

                cur.execute(query, tuple(params))
                data = cur.fetchall()

                if not data:
                    flash("No attendance records found for the selected criteria.", "info")

        # The rest of your code (except/finally/return) remains the same
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template('FAttendanceInfo.html', data=data, request_form=request_form)


# --- Fdownload_attendance route (ensure shift is passed) ---
@app.route('/Fdownload_attendance', methods=['POST'])
def Fdownload_attendance():
    conn = None
    cur = None
    try:
        depart = request.form.get('depart')
        batch = request.form.get('Batch')
        year = request.form.get('year')
        date = request.form.get('date')
        shift = request.form.get('shift') # Get shift from hidden input

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Could not download CSV.", "danger")
            return redirect(url_for('FAttendanceInfo'))

        cur = conn.cursor(buffered=True, dictionary=True)

        query = "SELECT Regno, Name, Department, Batch, Year, Datetime, Attendance, Shift FROM attentb WHERE 1=1"
        params = []

        if depart:
            query += " AND Department = %s"
            params.append(depart)
        if batch:
            query += " AND Batch = %s"
            params.append(batch)
        if year:
            query += " AND Year = %s"
            params.append(year)
        if date:
            query += " AND DATE(Datetime) = %s"
            params.append(date)
        if shift: # Add shift to download query
            query += " AND Shift = %s"
            params.append(shift)

        cur.execute(query, tuple(params))
        records = cur.fetchall()

        if not records:
            flash("No records to download for the selected criteria.", "info")
            return redirect(url_for('FAttendanceInfo'))

        si = io.StringIO()
        cw = csv.writer(si)

        # Write header row - Adjust column names if your DB schema is different
        cw.writerow(['Register No', 'Name', 'Department', 'Batch', 'Year', 'Date & Time', 'Attendance Status', 'Shift'])

        for record in records:
            # Format datetime object for CSV
            formatted_datetime = record[5].strftime('%Y-%m-%d %H:%M:%S') if record[5] else ''
            # Ensure correct order and inclusion of Shift
            cw.writerow([record[0], record[1], record[2], record[3], record[4], formatted_datetime, record[6], record[7]])

        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=attendance_records.csv"
        output.headers["Content-type"] = "text/csv"
        return output

    except mysql.connector.Error as err:
        flash(f"Database error during CSV download: {err}", "danger")
        return redirect(url_for('FAttendanceInfo'))
    except Exception as e:
        flash(f"An unexpected error occurred during CSV download: {e}", "danger")
        return redirect(url_for('FAttendanceInfo'))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Fdelete_attendance route (ensure shift is handled) ---
@app.route('/Fdelete_attendance', methods=['POST'])
def Fdelete_attendance():
    conn = None
    cur = None
    try:
        regno = request.form.get('regno')
        datetime_str = request.form.get('datetime')
        shift = request.form.get('shift') # Get shift from hidden input

        # Parse datetime string to datetime object
        attendance_datetime = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Could not delete record.", "danger")
            return redirect(url_for('FAttendanceInfo'))

        cur = conn.cursor(buffered=True, dictionary=True)

        # Delete query now includes Shift for unique identification
        cur.execute(
            "DELETE FROM attentb WHERE Regno = %s AND Datetime = %s AND Shift = %s",
            (regno, attendance_datetime, shift)
        )
        conn.commit()
        flash("Attendance record deleted successfully!", "success")

    except mysql.connector.Error as err:
        flash(f"Database error during deletion: {err}", "danger")
        conn.rollback()
    except Exception as e:
        flash(f"An unexpected error occurred during deletion: {e}", "danger")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Redirect back to the FAttendanceInfo page, possibly with previous filter applied
    # You might want to pass the filter parameters back here to pre-populate the form
    # For simplicity, redirecting without re-applying filters here.
    return redirect(url_for('FAttendanceInfo'))

@app.route('/Fattendancesearch', methods=['GET','POST'])
def Fattendancesearch():
    # Retrieve filter criteria from the form, with 'MCA' as default for department
    depart = request.form.get('depart', 'MCA')
    batch = request.form.get('Batch', '')
    year = request.form.get('year', '')
    date_filter = request.form.get('date', datetime.date.today().isoformat()) # Default to today's date
    shift = request.form.get('shift', '') # Add retrieval for shift, with empty string as default

    # Store form data to re-populate filter fields after submission
    request_form = {
        'depart': depart,
        'Batch': batch,
        'year': year,
        'date': date_filter,
        'shift': shift # Include shift in request_form
    }

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error. Please try again later.", "danger")
        return render_template('FAttendanceInfo.html', data=None, request_form=request_form)

    cur = conn.cursor(buffered=True, dictionary=True)  # Use buffered cursor
    attendance_records = []

    try:
        # Construct the base query
        query = """
            SELECT
                s.Registerno,
                s.Name,
                s.Department,
                s.Batch,
                s.Year,
                a.Datetime,
                a.Attendance,
                a.Shift
            FROM studenttb s
            JOIN attentb a ON s.Registerno = a.Regno
            WHERE 1=1
        """
        params = []

        # Add conditions based on provided filters
        if depart:
            query += " AND s.Department = %s"
            params.append(depart)
        if batch:
            query += " AND s.Batch = %s"
            params.append(batch)
        if year:
            query += " AND s.Year = %s"
            params.append(year)
        if date_filter:
            query += " AND DATE(a.Datetime) = %s"
            params.append(date_filter)
        if shift: # Add shift filter
            query += " AND a.Shift = %s"
            params.append(shift)

        query += " ORDER BY a.Datetime DESC, s.Registerno ASC;"

        cur.execute(query, tuple(params)) # Use tuple(params) when executing
        attendance_records = cur.fetchall()

        if not attendance_records:
            flash("No attendance records found for the selected criteria.", "info")

    except mysql.connector.Error as err:
        flash(f"Error searching attendance records: {err}", "danger")
        print(f"DB Error in Fattendancesearch: {err}")
    finally:
        if conn:
            cur.close()
            conn.close()

    return render_template('FAttendanceInfo.html', data=attendance_records, request_form=request_form)


# In your App.py (or wherever your Flask routes are defined)

# --- Your Fattendance route ---
@app.route('/Fattendance', methods=['GET', 'POST'])
def Fattendance():
    students_data = []
    request_form = {
        'depart': '',
        'Batch': '',
        'year': '',
        'date': datetime.date.today().isoformat(), # Default to today's date
        'shift': ''
    }
    attendance_status_map = {} # This will store pre-existing attendance

    if request.method == 'POST':
        # --- Handle Filter Submission (to load students) ---
        if 'submit_filter' in request.form:
            depart = request.form.get('depart')
            batch = request.form.get('Batch')
            year = request.form.get('year')
            date_str = request.form.get('date')
            shift = request.form.get('shift')

            # Store these values to re-populate the form fields
            request_form = {
                'depart': depart,
                'Batch': batch,
                'year': year,
                'date': date_str,
                'shift': shift
            }

            if not all([depart, batch, year, date_str, shift]):
                flash("Please select Department, Batch, Year, Date, and Shift to load students.", "warning")
            else:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)

                    # 1. Fetch all students for the selected class
                    cursor.execute("""
                        SELECT RegisterNo, Name
                        FROM studenttb
                        WHERE Department = %s AND Batch = %s AND Year = %s
                        ORDER BY RegisterNo
                    """, (depart, batch, year))
                    all_students = cursor.fetchall()

                    # 2. Fetch existing attendance for these students for the selected date and shift
                    # MODIFIED: Check for both 'Present' and 'IN' statuses for existing attendance
                    attendance_query = """
                        SELECT Regno
                        FROM attentb
                        WHERE Datetime LIKE %s AND Shift = %s AND Attendance IN ('Present', 'IN')
                    """
                    cursor.execute(attendance_query, (f"{date_str}%", shift))
                    existing_attendance_records = cursor.fetchall()

                    # Build the attendance_status_map
                    # Initialize all students as 'Absent' by default
                    for student_dict in all_students:
                        attendance_status_map[student_dict['RegisterNo']] = 'Absent'

                    # Mark students as 'Present' if an existing record is found
                    for record_dict in existing_attendance_records:
                        attendance_status_map[record_dict['Regno']] = 'Present'

                    # Prepare students_data for the template, including their initial status
                    students_data = []
                    for student_dict in all_students:
                        students_data.append({
                            'Registerno': student_dict['RegisterNo'],
                            'Name': student_dict['Name'],
                            'initial_status': attendance_status_map.get(student_dict['RegisterNo'], 'Absent')
                        })

                    request_form['attendance_status_map'] = attendance_status_map

                except mysql.connector.Error as err:
                    flash(f"Database error: {err}", "danger")
                    print(f"Error fetching students or attendance: {err}")
                except Exception as e:
                    flash(f"An unexpected error occurred: {e}", "danger")
                    print(f"UNEXPECTED ERROR in Fattendance (filter): {e}")
                finally:
                    if conn:
                        cursor.close()
                        conn.close()

        # --- Handle Save Attendance Submission ---
        elif 'submit_attendance' in request.form:
            depart = request.form.get('depart')
            batch = request.form.get('Batch')
            year = request.form.get('year')
            date_str = request.form.get('date')
            shift = request.form.get('shift')

            request_form = {
                'depart': depart,
                'Batch': batch,
                'year': year,
                'date': date_str,
                'shift': shift
            }

            if not all([depart, batch, year, date_str, shift]):
                flash("Filter criteria missing for saving attendance. Please re-select.", "warning")
            else:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)

                    # It's good practice to clear existing attendance for the class/date/shift
                    # before inserting new ones, to handle changes (e.g., student becomes absent)
                    # MODIFIED: Delete records with 'Present' or 'IN' status
                    delete_query = """
                        DELETE FROM attentb
                        WHERE Department = %s AND Batch = %s AND Year = %s
                        AND Datetime LIKE %s AND Shift = %s AND Attendance IN ('Present', 'IN')
                    """
                    cursor.execute(delete_query, (depart, batch, year, f"{date_str}%", shift))
                    conn.commit()
                    flash(f"Cleared existing attendance for {date_str} ({shift}).", "info")

                    # Iterate through all students' attendance checkboxes
                    cursor.execute("""
                        SELECT RegisterNo, Name, Mobile, Department, Batch, Year
                        FROM studenttb
                        WHERE Department = %s AND Batch = %s AND Year = %s
                    """, (depart, batch, year))
                    all_students_for_marking = cursor.fetchall()

                    for student_dict in all_students_for_marking:
                        regno = student_dict['RegisterNo']
                        name = student_dict['Name']
                        mobile = student_dict['Mobile']

                        attendance_key = f"attendance_status_{regno}"
                        status = request.form.get(attendance_key) # Will be 'Present' if checked, None otherwise

                        if status == 'Present':
                            insert_query = """
                                INSERT INTO attentb (Regno, Name, Mobile, Department, Batch, Year, Shift, Datetime, Attendance)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """
                            current_timestamp = datetime.datetime.now()
                            # MODIFIED: Insert 'IN' as the status when manually marked present
                            cursor.execute(insert_query, (regno, name, mobile, depart, batch, year, shift, current_timestamp, 'IN'))

                    conn.commit()
                    flash("Attendance saved successfully!", "success")

                    # Re-fetch students and their *new* attendance status to display updated state
                    cursor.execute("""
                        SELECT RegisterNo, Name
                        FROM studenttb
                        WHERE Department = %s AND Batch = %s AND Year = %s
                        ORDER BY RegisterNo
                    """, (depart, batch, year))
                    all_students = cursor.fetchall()

                    # MODIFIED: Check for both 'Present' and 'IN' statuses for existing attendance
                    attendance_query = """
                        SELECT Regno
                        FROM attentb
                        WHERE Datetime LIKE %s AND Shift = %s AND Attendance IN ('Present', 'IN')
                    """
                    cursor.execute(attendance_query, (f"{date_str}%", shift))
                    existing_attendance_records = cursor.fetchall()

                    attendance_status_map = {}
                    for student_dict in all_students:
                        regno = student_dict['RegisterNo']
                        attendance_status_map[regno] = 'Absent'

                    for record_dict in existing_attendance_records:
                        regno_from_attendance = record_dict['Regno']
                        attendance_status_map[regno_from_attendance] = 'Present'

                    students_data = []
                    for student_dict in all_students:
                        regno = student_dict['RegisterNo']
                        name = student_dict['Name']
                        students_data.append({
                            'Registerno': regno,
                            'Name': name,
                            'initial_status': attendance_status_map.get(regno, 'Absent')
                        })
                    request_form['attendance_status_map'] = attendance_status_map

                except mysql.connector.Error as err:
                    flash(f"Database error saving attendance: {err}", "danger")
                    print(f"Error saving attendance: {err}")
                    if conn: conn.rollback() # Rollback changes on error
                except Exception as e:
                    flash(f"An unexpected error occurred: {e}", "danger")
                    print(f"UNEXPECTED ERROR in Fattendance (save): {e}")
                finally:
                    if conn:
                        cursor.close()
                        conn.close()

    # Initial GET request or if no specific submit button was pressed
    return render_template('Fattendance.html', students_data=students_data, request_form=request_form)


@app.route('/NewStudent')
def NewStudent():
    import LiveRecognition as liv
    liv.att()
    del sys.modules["LiveRecognition"]
    return render_template('NewStudent.html')


@app.route("/newstudent", methods=['GET', 'POST'])
def newstudent():
    # Initialize request_form to hold submitted data for re-population
    # This will be populated with request.form on POST if validation fails
    # On GET, it will be empty, so fields appear blank
    request_form_data = {}

    if request.method == 'POST':
        regno = request.form.get('regno', '').strip()
        uname = request.form.get('uname', '').strip()
        gender = request.form.get('gender', '').strip()
        mobile = request.form.get('mobile', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('Address', '').strip()
        depart = request.form.get('depart', '').strip()
        Batch = request.form.get('Batch', '').strip()
        year = request.form.get('year', '').strip()
        raw_password = request.form.get('password', '') # New password field

        # Populate request_form_data with current form submission for re-rendering
        request_form_data = {
            'regno': regno, 'uname': uname, 'gender': gender, 'mobile': mobile,
            'email': email, 'Address': address, 'depart': depart,
            'Batch': Batch, 'year': year
            # Do NOT include raw_password here for security reasons
        }

        errors = [] # List to collect validation errors

        # --- Server-Side Validation ---
        if not regno:
            errors.append("Registration Number is required.")
        if not uname:
            errors.append("Student Name is required.")
        if not gender:
            errors.append("Gender is required.")
        if not mobile:
            errors.append("Mobile Number is required.")
        elif not mobile.isdigit() or len(mobile) != 10:
            errors.append("Mobile Number must be exactly 10 digits.")
        if not email:
            errors.append("Email is required.")
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("Please enter a valid Email Address.")
        if not address:
            errors.append("Address is required.")
        if not depart:
            errors.append("Department is required.")
        if not Batch:
            errors.append("Batch is required.")
        if not year:
            errors.append("Year is required.")
        if not raw_password:
            errors.append("Password is required.")
        elif len(raw_password) < 6:
            errors.append("Password must be at least 6 characters long.")
        elif not re.search(r"\d", raw_password):
            errors.append("Password must contain at least one number.")
        elif not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", raw_password):
            errors.append("Password must contain at least one special character (e.g., !@#$%^&*).")


        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if conn is None:
                errors.append("Failed to connect to the database. Please try again later.")
                # Flash errors and return if DB connection fails
                for error in errors:
                    flash(error, "danger")
                return render_template('newstudent.html', request_form=request_form_data)

            cursor = conn.cursor()

            # Check for duplicate Registration Number or Email in the database
            cursor.execute("SELECT COUNT(*) FROM studenttb WHERE RegisterNo = %s OR Email = %s", (regno, email))
            if cursor.fetchone()[0] > 0:
                errors.append("Registration Number or Email already exists. Please use a different one.")

            # If any validation errors (including DB uniqueness check), flash them and re-render
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template('newstudent.html', request_form=request_form_data)

            # Hash the password before storing
            hashed_password = generate_password_hash(raw_password)

            # Insert student data into studenttb, including the new password_hash column
            cursor.execute("""
                INSERT INTO studenttb
                (RegisterNo, Name, Gender, Mobile, Email, Address, Department, Batch, Year, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (regno, uname, gender, mobile, email, address, depart, Batch, year, hashed_password))
            conn.commit()

            flash("Student registered successfully!", "success")
            # Redirect to FStudentInfo to show the updated list of students
            return redirect(url_for('FStudentInfo'))

        except mysql.connector.Error as err:
            flash(f"Database error registering student: {err}", "danger")
            current_app.logger.error(f"Database error during student registration: {err}")
            if conn:
                conn.rollback() # Rollback changes if an error occurs
            return render_template('newstudent.html', request_form=request_form_data)

        except Exception as e:
            flash(f"An unexpected error occurred during registration: {e}", "danger")
            current_app.logger.error(f"Unexpected error in newstudent POST: {e}")
            return render_template('newstudent.html', request_form=request_form_data)

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # For GET requests (initial load of the form)
    # request_form_data will be empty, so fields will be blank
    return render_template('newstudent.html', request_form=request_form_data)


@app.route("/attendance", methods=['GET', 'POST'])
def attendance():
    if request.method == 'POST':
        if request.form["submit"] == "submit":
            date = datetime.datetime.now()
            check = request.form.getlist("check")
            check1 = request.form.getlist("check1")

            for m in check1:
                conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8')
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM studenttb WHERE RegisterNo = %s", (m,))
                data = cursor.fetchone()

                if data:
                    regno = data[1]
                    name = data[2]
                    Mobile = data[4]
                    Department = data[7]
                    Batch = data[8]
                    Year = data[9]

                    attendance_status = '1' if m in check else '0'
                    message = "Your Son Or daughter Present today" if attendance_status == '1' else "Your Son Or daughter Absent today"
                    sendmsg(Mobile, message)

                    cursor.execute("""
                        INSERT INTO attentb (Regno, Name, Mobile, Department, Batch, Year, DateTime, Attendance)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (regno, name, Mobile, Department, Batch, Year, date, attendance_status))
                    conn.commit()
                conn.close()

            flash("Record Saved!")
            return render_template('FAttendance.html')

        else:
            depart = request.form['depart']
            Batch = request.form['Batch']
            year = request.form['year']

            conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8' )
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM studenttb 
                WHERE Department = %s AND Batch = %s AND year = %s
            """, (depart, Batch, year))
            data = cur.fetchall()
            conn.close()
            return render_template('FAttendance.html', data=data)


@app.route("/attendancesearch", methods=['GET', 'POST'])
def attendancesearch():
    if request.method == 'POST':
        depart = request.form['depart']
        Batch = request.form['Batch']
        year = request.form['year']
        date1 = request.form['date']
        date = datetime.datetime.strptime(date1, '%Y-%m-%d')

        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb',charset='utf8')
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM attentb 
            WHERE DATE(DateTime) = %s AND Department = %s AND Batch = %s AND Year = %s
        """, (date, depart, Batch, year))
        data = cur.fetchall()
        conn.close()
        return render_template('FAttendanceInfo.html', data=data)



@app.route("/Remove")
def Remove():
    id = request.args.get('id')

    conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb',charset='utf8')
    cursor = conn.cursor()
    cursor.execute("delete from  studenttb  where id='" + id + "' ")
    conn.commit()
    conn.close()

    conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8')
    cur = conn.cursor()
    cur.execute("SELECT * FROM studenttb ")
    data = cur.fetchall()

    return render_template('FStudentInfo.html', data=data)


@app.route("/AUserSearch", methods=['GET', 'POST'])
def AUserSearch():
    if request.method == 'POST' and request.form["submit"] == "Close":
        date = request.form['date']

        # Establish connection only once
        conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8')
        cursor = conn.cursor()

        # Fetch students data
        cursor.execute("SELECT * FROM studenttb")
        students_data = cursor.fetchall()

        out1 = ''
        out2 = ''

        for student in students_data:
            regno = student[1]
            name = student[2]
            Mobile = student[4]
            Department = student[7]
            Batch = student[8]
            Year = student[9]

            print(regno)

            # Use the same cursor to check attendance
            conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb',charset='utf8')
            cursor = conn.cursor()

            # Fetch students data
            cursor.execute("SELECT * FROM attentb where DateTime='"+ date +"' and Regno='"+ regno +"' ")
            attendance_data = cursor.fetchone()

            if attendance_data is None:
                # Insert new attendance record
                conn = mysql.connector.connect(user='root', password='', host='localhost',
                                               database='1faceattandanceinoutdb', charset='utf8')
                cursor = conn.cursor()
                cursor.execute(
                    "insert into attentb values('','" + regno + "','" + name + "','" + Mobile + "','" + Department + "','" + Batch + "','" + Year + "' ,'" + str(
                        date) + "','Absent')")
                conn.commit()
                conn.close()
                flash("Attendance not recorded for today")

                reg = student[1]
                sname = student[2]
                if out2 == "":
                    out2 = f"Absent details Regno {reg} Student name {sname}"
                else:
                    out2 += f" Regno {reg} Student name {sname}"

                # sendmsg('9087259509', "Your Not attend college today")  # Uncomment if you have a function to send messages
            else:
                flash("Attendance already recorded")
                reg = attendance_data[1]
                sname = attendance_data[2]
                if out1 == "":
                    out1 = f"Present details Regno {reg} Student name {sname}"
                else:
                    out1 += f" Regno {reg} Student name {sname}"

        email = session.get('email', '')  # Use .get() to avoid KeyError if email is missing
        print(email)
        print(out1)
        print(out2)
        sendmail(email, f"{out1}, {out2}")
        #conn.commit()  # Commit after all operations
        return render_template('Fattendance.html', data=attendance_data)

def sendmail(Mailid, message):
    print(Mailid)
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    fromaddr = "projectmailm@gmail.com"
    toaddr = Mailid

    # instance of MIMEMultipart
    msg = MIMEMultipart()

    # storing the senders email address
    msg['From'] = fromaddr

    # storing the receivers email address
    msg['To'] = toaddr

    # storing the subject
    msg['Subject'] = "Alert"

    # string to store the body of the mail
    body = message

    # attach the body with the msg instance
    msg.attach(MIMEText(body, 'plain'))

    # creates SMTP session
    s = smtplib.SMTP('smtp.gmail.com', 587)

    # start TLS for security
    s.starttls()

    # Authentication
    s.login(fromaddr, "qmgn xecl bkqv musr")

    # Converts the Multipart msg into a string
    text = msg.as_string()

    # sending the mail
    s.sendmail(fromaddr, toaddr, text)

    # terminating the session
    s.quit()


@app.route("/studentlogin", methods=['GET', 'POST'])
def studentlogin():
    if request.method == 'POST':
        rno = request.form.get('rno')  # Use .get() for safer access
        email = request.form.get('email')

        if not rno or not email:
            flash("Please enter both Register Number and Email.", "warning")
            return render_template('StudentLogin.html')

        conn = get_db_connection()
        if conn is None:
            # If DB connection fails, redirect to a safer page or show an error
            flash("Database connection error. Please try again later.", "danger")
            return render_template('StudentLogin.html') # Or redirect to a general error page

        cursor = conn.cursor()
        try:
            # Query the studenttb table
            # Assuming 'RegisterNo' and 'Email' are the correct column names for student login
            cursor.execute("SELECT Registerno, Name, Email FROM studenttb WHERE Registerno=%s AND Email=%s", (rno, email))
            student_data = cursor.fetchone()

            if student_data:
                # Login successful
                session['loggedin'] = True
                session['rno'] = student_data[0] # Register Number
                session['student_name'] = student_data[1] # Student Name
                session['student_email'] = student_data[2] # Student Email (if needed later)
                session['role'] = 'student' # Indicate the user's role

                flash(f"Welcome, {student_data[1]}! You are successfully logged in.", "success")
                return redirect(url_for('StudentHome')) # Redirect to your student dashboard route
            else:
                # Login failed
                flash("Invalid Register Number or Email.", "danger")
                return render_template('StudentLogin.html') # Re-render login page
        except mysql.connector.Error as err:
            flash(f"Database error during login: {err}", "danger")
            return render_template('StudentLogin.html')
        finally:
            if conn:
                cursor.close()
                conn.close()

    # For GET requests (when the page is first loaded)
    return render_template('StudentLogin.html')

def calculate_overall_attendance_for_period(rno, start_date_str, end_date_str):
    """
    Calculates overall attendance percentage, present days, and absent days
    for a specific student within a given date range.
    The end_date_str will be today's date.
    """
    conn = get_db_connection()
    if conn is None:
        print("DEBUG: calculate_overall_attendance_for_period: No DB connection.")
        return 0, 0, 0 # Default values if no connection

    cur = conn.cursor(buffered=True)
    try:
        # Convert date strings to datetime.date objects for calculations
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Calculate total possible days in the range (inclusive, up to today)
        total_possible_days = (end_date - start_date).days + 1

        # Ensure total_possible_days is not negative in case of invalid date range
        if total_possible_days < 0:
            total_possible_days = 0
            print(f"DEBUG: total_possible_days calculated as negative. Adjusted to 0. start={start_date}, end={end_date}")

        print(f"DEBUG: Calculating attendance for RNO: {rno}")
        print(f"DEBUG: Period: {start_date_str} to {end_date_str}")
        print(f"DEBUG: Total possible days in period: {total_possible_days}")

        # Fetch attendance records for the specific student within the dynamic date range
        cur.execute("""
            SELECT Datetime, Attendance
            FROM attentb
            WHERE Regno = %s
            AND DATE(Datetime) BETWEEN %s AND %s
            ORDER BY Datetime DESC
        """, (rno, start_date_str, end_date_str))
        attendance_records_in_period = cur.fetchall()

        print(f"DEBUG: Raw attendance records fetched ({len(attendance_records_in_period)} records):")
        for record in attendance_records_in_period:
            print(f"  - {record}")

        # --- THIS IS THE CRUCIAL CHANGE: Define valid 'present' indicators. Include 'IN' ---
        present_indicators = ['present', 'p', 'attended', 'in']
        present_days = sum(1 for record in attendance_records_in_period if record[1] and record[1].lower() in present_indicators)
        print(f"DEBUG: Counted present days: {present_days}")

        # Absent days are now based on total possible days up to today
        absent_days = total_possible_days - present_days
        print(f"DEBUG: Counted absent days (total_possible - present): {absent_days}")

        percentage = (present_days / total_possible_days) * 100 if total_possible_days > 0 else 0
        print(f"DEBUG: Calculated percentage: {percentage}")

        return round(percentage, 2), present_days, absent_days

    except mysql.connector.Error as err:
        print(f"DATABASE ERROR in calculate_overall_attendance_for_period: {err}")
        return 0, 0, 0
    except Exception as e:
        print(f"UNEXPECTED ERROR in calculate_overall_attendance_for_period: {e}")
        return 0, 0, 0
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# --- Core Routes (ensure these are at the top-level indentation) ---
@app.route('/StudentHome')
def StudentHome():
    # Ensure 'app' is defined globally or passed if this is part of a larger Flask app
    # For a complete Flask app, 'app' would be your Flask(__name__) instance.
    # If this is a snippet, assume 'app' is accessible.

    rno = session.get('rno')  # Use .get() for safer access
    if not rno:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login')) # Redirect to login if rno is not in session

    print(f"DEBUG: StudentHome accessed for RNO: {rno}")

    # Define the specific attendance period (May 16, 2025 up to today)
    start_date_period = "2025-05-16"
    end_date_period = datetime.date.today().strftime('%Y-%m-%d')
    print(f"DEBUG: Defined attendance period: {start_date_period} to {end_date_period}")

    # Initialize variables for template
    student_data = None
    attendance_records = []
    leave_requests = []
    overall_attendance_percentage = 0.0
    period_present_days = 0
    period_absent_days = 0
    # total_leaves_taken is removed as per request

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error. Please try again later.", "danger")
        print("DEBUG: StudentHome: No DB connection established.")
        return render_template('StudentHome.html',
                               student_data=student_data,
                               attendance_records=attendance_records,
                               leave_requests=leave_requests,
                               attendance_percentage=overall_attendance_percentage,
                               total_present_days=period_present_days,
                               total_absent_days=period_absent_days) # Removed total_leaves_taken

    cur = conn.cursor(buffered=True)
    try:
        # 1. Fetch Student Profile Data
        cur.execute(
            "SELECT Registerno, Name, Gender, Mobile, Email, Address, Department, Batch, Year FROM studenttb WHERE Registerno=%s",
            (rno,))
        student_data = cur.fetchone()

        if not student_data:
            flash("Your student profile data could not be found. Please contact administration.", "danger")
            print(f"DEBUG: Student profile data not found for RNO: {rno}. Redirecting to logout.")
            return redirect(url_for('logout'))
        print(f"DEBUG: Student data fetched: {student_data}")

        # 2. Calculate Overall Attendance for the specified period (May 16 - Today)
        overall_attendance_percentage, period_present_days, period_absent_days = \
            calculate_overall_attendance_for_period(rno, start_date_period, end_date_period)

        print(f"DEBUG: Overall Attendance Summary - Present: {period_present_days}, Absent: {period_absent_days}, Percentage: {overall_attendance_percentage}%")

        # 3. Fetch Recent Attendance Records (e.g., last 10 records)
        # Showing recent attendance within the calculated period
        cur.execute("""
            SELECT Datetime, Attendance
            FROM attentb
            WHERE Regno=%s
            AND DATE(Datetime) BETWEEN %s AND %s
            ORDER BY Datetime DESC
            LIMIT 10
        """, (rno, start_date_period, end_date_period)) # Filter recent by the current period
        attendance_records = cur.fetchall()
        print(f"DEBUG: Recent attendance records fetched ({len(attendance_records)} records).")

        # 4. Fetch Student Leave Requests History
        cur.execute("""
            SELECT id, start_date, end_date, reason, status, request_date
            FROM leave_requests
            WHERE student_id=%s
            ORDER BY request_date DESC
        """, (rno,))
        leave_requests = cur.fetchall()
        print(f"DEBUG: Leave requests fetched ({len(leave_requests)} records).")

        # 5. Removed: Count Total Approved Leaves for summary
        # The following lines are removed as per your request:
        # cur.execute("SELECT COUNT(*) FROM leave_requests WHERE student_id = %s AND status = 'Approved'", (rno,))
        # leaves_count_result = cur.fetchone()
        # if leaves_count_result:
        #     total_leaves_taken = leaves_count_result[0]
        # print(f"DEBUG: Total approved leaves: {total_leaves_taken}")

    except mysql.connector.Error as err:
        flash(f"Error fetching your data: {err}", "danger")
        print(f"DATABASE ERROR in StudentHome for student {rno}: {err}")

    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        print(f"UNEXPECTED ERROR in StudentHome: {e}")

    finally:
        if cur: cur.close()
        if conn: conn.close()

    print(f"DEBUG: Rendering StudentHome.html with:")
    print(f"  student_data: {'present' if student_data else 'absent'}")
    print(f"  attendance_percentage: {overall_attendance_percentage}")
    print(f"  total_present_days: {period_present_days}")
    print(f"  total_absent_days: {period_absent_days}")
    # total_leaves_taken is no longer printed or passed

    return render_template(
        'StudentHome.html',
        student_data=student_data,
        attendance_records=attendance_records,
        leave_requests=leave_requests,
        attendance_percentage=overall_attendance_percentage,
        total_present_days=period_present_days,
        total_absent_days=period_absent_days
        # total_leaves_taken is removed from here
    )


@app.route("/SAttendanceInfo")
def SAttendanceInfo():
    rno = session['rno']
    leaves = []  # List to hold leave request data

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error. Please try again later.", "danger")
        return render_template('your_attendance_info_template.html', leaves=leaves)  # Or redirect
    cur = conn.cursor()
    try:
        # Fetch detailed leave history for SAttendanceInfo page
        cur.execute("""
            SELECT id, start_date, end_date, reason, status, request_date
            FROM leave_requests
            WHERE student_id=%s
            ORDER BY request_date DESC
        """, (rno,))
        leaves = cur.fetchall()

    except mysql.connector.Error as err:
        flash(f"Error fetching leave history: {err}", "danger")
        print(f"Database error in SAttendanceInfo for student {rno}: {err}")
    finally:
        if conn:
            cur.close()
            conn.close()

    # You'll need a dedicated template for SAttendanceInfo if it's not the main dashboard
    return render_template('your_attendance_info_template.html', leaves=leaves)


# Make sure you have 'datetime' imported at the top of your App.py:
# import datetime
# from datetime import datetime, date

# --- Leave Request Form Route (GET) ---
@app.route("/leave_request_form", methods=['GET']) # Only GET method for displaying the form
def show_leave_request_form():
    student_id = session.get('rno')

    if not student_id:
        flash("Please login to access this page.", "info")
        return redirect(url_for('studentlogin'))

    conn = None
    cur = None
    student_info = None # Initialize student_info as None

    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return render_template('leave_request_form.html', student_info=None)

        cur = conn.cursor(buffered=True) # Use buffered cursor if you plan to fetch multiple results or check row counts

        # Fetch student details for display on the form
        cur.execute("SELECT Registerno, Name, Department, Batch, Year FROM studenttb WHERE Registerno = %s", (student_id,))
        student_info = cur.fetchone() # Fetches a single row

        if not student_info:
            flash("Student data not found.", "danger")
            # Consider logging this as an error as student_id exists in session but not DB
            return redirect(url_for('studentlogin'))

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")
        print(f"DB Error in show_leave_request_form: {err}")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        print(f"Unexpected error in show_leave_request_form: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Pass the fetched student_info to the template
    return render_template('leave_request_form.html', student_info=student_info)


# --- Submit Leave Request Route (POST) ---
# In your App.py file, locate the request_leave function:

# In your App.py file, locate the request_leave function:

@app.route("/request_leave", methods=['POST'])
def request_leave():
    if request.method == 'POST':
        # Removed 'leave_type' from here, as it's not in your table schema
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        reason = request.form.get('reason')
        student_id = session.get('rno')

        # Updated validation message since 'leave_type' is no longer expected
        if not all([start_date_str, end_date_str, reason, student_id]):
            flash("All fields (Start Date, End Date, Reason) are required for leave request.", "danger")
            return redirect(url_for('show_leave_request_form'))

        conn = None
        cur = None
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

            if start_date > end_date:
                flash("End date cannot be before start date.", "danger")
                return redirect(url_for('show_leave_request_form'))

            conn = get_db_connection()
            if conn is None:
                flash("Database connection error. Please try again later.", "danger")
                return redirect(url_for('show_leave_request_form'))

            cur = conn.cursor()
            # CORRECTED INSERT STATEMENT:
            # 1. 'leave_type' column removed
            # 2. Column names corrected to lowercase with underscores (start_date, end_date, request_date)
            # 3. 'status' column enclosed in backticks (`status`) and corrected to lowercase
            cur.execute("""
                INSERT INTO leave_requests (student_id, start_date, end_date, reason, request_date, `status`)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (student_id, start_date, end_date, reason, datetime.date.today(), 'Pending'))
            # CORRECTED: Only 6 values are passed now, corresponding to the 6 columns in the INSERT statement

            conn.commit()
            flash("Your leave request has been submitted successfully and is pending approval.", "success")
            return redirect(url_for('StudentHome'))

        except ValueError:
            flash("Invalid date format. Please use Zanzibar-MM-DD.", "danger")
            return redirect(url_for('show_leave_request_form'))
        except mysql.connector.Error as err:
            flash(f"Error submitting leave request: {err}", "danger")
            print(f"Database error submitting leave request for {student_id}: {err}")
            if conn:
                conn.rollback()
            return redirect(url_for('show_leave_request_form'))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
            print(f"Unexpected error in request_leave: {e}")
            return redirect(url_for('show_leave_request_form'))
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return redirect(url_for('show_leave_request_form'))


@app.route("/saattendancesearch", methods=['GET', 'POST'])
def saattendancesearch():
    if request.method == 'POST':
        depart = request.form['depart']
        Batch = request.form['Batch']
        year = request.form['year']
        rno = session['rno']

        # Ensure datetime module is imported at the top of App.py
        # from datetime import datetime

        date1 = request.form['datetime']
        search_date_obj = datetime.datetime.strptime(date1, '%Y-%m-%d')

        conn = None  # Initialize conn to None
        cur = None  # Initialize cur to None
        try:
            # It's recommended to use get_db_connection() here for consistency
            conn = get_db_connection()
            if conn is None:
                flash("Could not connect to the database. Please try again later.", "danger")
                return render_template('saattendancesearch_form.html')  # Or redirect

            cur = conn.cursor()

            # Corrected SQL query using parameterized placeholders
            search_query = """
            SELECT * FROM attentb
            WHERE Datetime LIKE %s AND Department = %s AND Batch = %s AND Year = %s AND Regno = %s
            """
            # Using LIKE %s for Datetime with a wildcard to match any time component for that date.
            # search_date_obj.strftime('%Y-%m-%d%%') will create a string like '2025-06-01%'

            cur.execute(search_query, (search_date_obj.strftime('%Y-%m-%d%%'), depart, Batch, year, rno))

            data = cur.fetchall()

            if data:
                # Assuming you render a template with the results
                return render_template('saattendancesearch_results.html', data=data)
            else:
                flash("No attendance records found for the given criteria.", "info")
                return render_template('saattendancesearch_form.html')  # Or redirect to form

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
            print(f"Database error in saattendancesearch: {err}")
            return render_template('error.html')  # Or handle error appropriately
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    # Handle GET request for the form
    return render_template('saattendancesearch_form.html')  # Assuming you have a form template


if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)
