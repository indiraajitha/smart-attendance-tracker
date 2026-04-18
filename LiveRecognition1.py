from flask import Flask, render_template, flash, request, session
import sys, fsdk, math, ctypes, time
from fsdk import FSDK
import mysql.connector
import datetime
import time
import winsound


# def examvales(ExamName,SubjectName,Date,Degree,Department,Year11):
def examvales():
    global ExamName1
    global SubjectName1
    global Date1
    global Degree1
    global Department1
    global Year1

    attendance_marked_and_stop = False  # <--- ADD THIS LINE HERE

# license_key = "fVrFCzYC5wOtEVspKM/zfLWVcSIZA4RNqx74s+QngdvRiCC7z7MHlSf2w3+OUyAZkTFeD4kSpfVPcRVIqAKWUZzJG975b/P4HNNzpl11edXGIyGrTO/DImoZksDSRs6wktvgr8lnNCB5IukIPV5j/jBKlgL5aqiwSfyCR8UdC9s="
# (Using the license key directly in the file, consider loading from config/env var)
license_key = "fVrFCzYC5wOtEVspKM/zfLWVcSIZA4RNqx74s+QngdvRiCC7z7MHlSf2w3+OUyAZkTFeD4kSpfVPcRVIqAKWUZzJG975b/P4HNNzpl11edXGIyGrTO/DImoZksDSRs6wktvgr8lnNCB5IukIPV5j/jBKlgL5aqiwSfyCR8UdC9s="


if not fsdk.windows:
    print('The program is for Microsoft Windows.');
    exit(1)
import win

trackerMemoryFile = "tracker70.dat"

FONT_SIZE = 30

print("Initializing FSDK... ", end='')
FSDK.ActivateLibrary(license_key);
FSDK.Initialize()
print("OK\nLicense info:", FSDK.GetLicenseInfo())

FSDK.InitializeCapturing()
print('Looking for video cameras... ', end='')
camList = FSDK.ListCameraNames()

if not camList: print("Please attach a camera.");
print(camList[0]) # camList[0].devicePath

camera = camList[0] # choose the first camera (0)
print("using '%s'" % camera)
formatList = FSDK.ListVideoFormats(camera)
print(*formatList[0:5], sep='\n')
if len(formatList) > 5: print('...', len(formatList) - 5, 'more formats (skipped)...')

vfmt = formatList[4] # choose the first format: vfmt.Width, vfmt.Height, vfmt.BPP
print('Selected camera format:', vfmt)
FSDK.SetVideoFormat(camera, vfmt)

print("Trying to open '%s'... " % camera, end='')
camera = FSDK.OpenVideoCamera(camera)
print("OK", camera.handle)

try:
    fsdkTracker = FSDK.Tracker.FromFile(trackerMemoryFile)
except:
    fsdkTracker = FSDK.Tracker() # creating a FSDK Tracker

fsdkTracker.SetParameters( # set realtime face detection parameters
    RecognizeFaces=True, DetectFacialFeatures=True,
    HandleArbitraryRotations=True, DetermineFaceRotationAngle=False,
    InternalResizeWidth=256, FaceDetectionThreshold=5
)

need_to_exit = False

def WndProc(hWnd, message, wParam, lParam):
    global capturedFace
    if message == win.WM_CTLCOLOREDIT:
        fsdkTracker.SetName(capturedFace, win.GetWindowText(inpBox))
    if message == win.WM_DESTROY:
        global need_to_exit
        need_to_exit = True
    else:
        if message == win.WM_MOUSEMOVE:
            updateActiveFace()
            return 1
        if message == win.WM_LBUTTONDOWN:
            if activeFace and capturedFace != activeFace:
                capturedFace = activeFace
                win.SetWindowText(inpBox, fsdkTracker.GetName(capturedFace))
                win.ShowWindow(inpBox, win.SW_SHOW)
                win.SetFocus(inpBox)
            else:
                capturedFace = None
                win.ShowWindow(inpBox, win.SW_HIDE)
            return 1
    return win.DefWindowProc(hWnd, message, win.WPARAM(wParam), win.LPARAM(lParam))


wcex = win.WNDCLASSEX(cbSize=ctypes.sizeof(win.WNDCLASSEX), style=0, lpfnWndProc=win.WNDPROC(WndProc),
                      cbClsExtra=0, cbWndExtra=0, hInstance=0, hIcon=0, hCursor=win.LoadCursor(0, win.IDC_ARROW),
                      hbrBackground=0,
                      lpszMenuName=0, lpszClassName=win.L("My Window Class"), hIconSm=0)
win.RegisterClassEx(wcex)

hwnd = win.CreateWindowEx(win.WS_EX_CLIENTEDGE, win.L("My Window Class"), win.L("Live Recognition"),
                          win.WS_SYSMENU | win.WS_CAPTION | win.WS_CLIPCHILDREN,
                          100, 100, vfmt.Width, vfmt.Height, *[0] * 4)
win.ShowWindow(hwnd, win.SW_SHOW)

inpBox = win.CreateWindow(win.L("EDIT"), win.L(""), win.SS_CENTER | win.WS_CHILD, 0, 0, 0, 0, hwnd, 0, 0, 0)
myFont = win.CreateFont(30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, win.L("Microsoft Sans Serif"))
win.SendMessage(inpBox, win.WM_SETFONT, myFont, True);
win.SetWindowPos(inpBox, 0, 0, vfmt.Height - 80, vfmt.Width, 80, win.SWP_NOZORDER)
win.UpdateWindow(hwnd)


def dot_center(dots): # calc geometric center of dots
    return sum(p.x for p in dots) / len(dots), sum(p.y for p in dots) / len(dots)


class LowPassFilter: # low pass filter to stabilize frame size
    def __init__(self, a=0.35): self.a, self.y = a, None
    def __call__(self, x): self.y = self.a * x + (1 - self.a) * (self.y or x); return self.y


class FaceLocator:
    def __init__(self, fid):
        self.lpf = None
        self.center = self.angle = self.frame = None
        self.fid = fid

    def isIntersect(self, state):
        (x1, y1, x2, y2), (xx1, yy1, xx2, yy2) = self.frame, state.frame
        return not (x1 >= xx2 or x2 < xx1 or y1 >= yy2 or y2 < yy1)

    def isActive(self):
        return self.lpf is not None

    def is_inside(self, x, y):
        x -= self.center[0]; y -= self.center[1]
        a = self.angle * math.pi / 180
        x, y = x * math.cos(a) + y * math.sin(a), x * math.sin(a) - y * math.cos(a)
        return (x / self.frame[0])**2 + (y / self.frame[1])**2 <= 1

    def draw_shape(self, surf):
        container = surf.beginContainer()
        surf.translateTransform(*self.center).rotateTransform(self.angle).ellipse(facePen, *self.frame) # draw frame
        if activeFace == self.fid:
            surf.ellipse(faceActivePen, *self.frame) # draw active frame
        if capturedFace == self.fid:
            surf.ellipse(faceCapturedPen, *self.frame) # draw captured frame
        surf.endContainer(container)

    def draw(self, surf, path, face_id=None):
        if face_id is not None:
            ff = fsdkTracker.GetFacialFeatures(0, face_id)
            if self.lpf is None: self.lpf = LowPassFilter()
            xl, yl = dot_center([ff[k] for k in FSDK.FSDKP_LEFT_EYE_SET])
            xr, yr = dot_center([ff[k] for k in FSDK.FSDKP_RIGHT_EYE_SET])
            w = self.lpf((xr - xl) * 2.8)
            h = w * 1.4
            self.center = (xr + xl) / 2, (yr + yl) / 2 + w * 0.05
            self.angle = math.atan2(yr - yl, xr - xl) * 180 / math.pi
            self.frame = -w / 2, -h / 2, w / 2, h / 2

            self.draw_shape(surf)

            name = fsdkTracker.GetName(self.fid)
            surf.drawString(name, font, self.center[0] - w / 2 + 2, self.center[1] - h / 2 + 2, text_shadow)
            surf.drawString(name, font, self.center[0] - w / 2, self.center[1] - h / 2, text_color)
        else:
            if self.lpf is not None: self.lpf, self.countdown = None, 35
            self.countdown -= 1
            if self.countdown <= 8:
                self.frame = [v * 0.95 for v in self.frame]
            else:
                self.draw_shape(surf)
            name = 'Unkown User!';
        path.ellipse(*self.frame) # frame background
        return self.lpf or self.countdown > 0


activeFace = capturedFace = None

def updateActiveFace():
    global activeFace
    p = win.ScreenToClient(hwnd, win.GetCursorPos())
    for fid, tr in trackers.items():
        if tr.center is not None and tr.is_inside(p.x, p.y):  # <--- MODIFIED LINE

            activeFace = fid
            break
    else:
        activeFace = None


gdiplus = win.GDIPlus() # initialize GDI+
graphics = win.Graphics(hwnd=hwnd)
backsurf = win.Bitmap.FromGraphics(vfmt.Width, vfmt.Height, graphics)
surfGr = win.Graphics(bmp=backsurf).setSmoothing(True) # graphics object for back surface with antialiasing
facePen, featurePen, brush = win.Pen(0x60ffffff, 5), win.Pen(0xa060ff60, 1.8), win.Brush(0x28ffffff)
faceActivePen, faceCapturedPen = win.Pen(0xFF00ff00, 2), win.Pen(0xFFff0000, 3)
font = win.Font(win.FontFamily("Tahoma"), FONT_SIZE)
text_color, text_shadow = win.Brush(0xffffffff), win.Brush(0xff808080)

trackers = {}

def sendmsg(targetno,message):
    import requests
    # Note: Using f-string for better readability and safety if message content is controlled.
    requests.post(
        f"http://sms.creativepoint.in/api/push.json?apikey=6555c521622c1&route=transsms&sender=FSSMSS&mobileno={targetno}&text=Dear customer your msg is {message}  Sent By FSMSG FSSMSS")


# --- Database Connection Initialization (Outside the loop) ---
db_conn = None
db_cursor = None
try:
    db_conn = mysql.connector.connect(user='root', password='', host='localhost', database='1faceattandanceinoutdb', charset='utf8')
    db_cursor = db_conn.cursor()
except mysql.connector.Error as err:
    print(f"Error connecting to database: {err}")
    # Consider exiting or handling this error more gracefully
    sys.exit(1)


sampleNum = 0
while 1:
    sampleNum = sampleNum + 1
    img = camera.GrabFrame()
    surfGr.resetClip().drawImage(win.Bitmap.FromHBITMAP(img.GetHBitmap())) # fill backsurface with image

    faces = frozenset(fsdkTracker.FeedFrame(0, img)) # recognize all faces in the image
    for face_id in faces.difference(trackers): trackers[face_id] = FaceLocator(face_id) # create new trackers

    missed, gpath = [], win.GraphicsPath()
    # In LiveRecognition1.py, around the `for face_id, tracker in trackers.items():` loop:

    # ... (previous code) ...

    for face_id, tracker in trackers.items():  # iterate over current trackers
        ss = fsdkTracker.GetName(face_id)
        ts = time.time()
        current_datetime = datetime.datetime.fromtimestamp(ts)  # Get full datetime object
        current_date_str = current_datetime.strftime('%Y-%m-%d')  # Only date string for comparison if needed

        # --- Use the pre-established database connection and cursor ---
        if db_conn and db_cursor:
            try:
                # Get student details from studenttb
                # Note: 'Shift' is NOT selected here because it's not in studenttb
                db_cursor.execute("""
                        SELECT 
                            id, RegisterNo, Name, Gender, Mobile, Email, Address,
                            Department, Batch, Year
                        FROM studenttb WHERE RegisterNo = %s
                    """, (str(ss),))
                data = db_cursor.fetchone()

                if data:  # Data access happens ONLY if a record is found
                    # Assign variables from the fetched data tuple based on studenttb schema
                    # In LiveRecognition1.py, inside the 'if data:' block where you define variables:

                    # ... (previous variable assignments from data tuple) ...
                    regno = data[1]  # RegisterNo
                    name = data[2]  # Name
                    Mobile = data[4]  # Mobile
                    Department = data[7]  # Department
                    Batch = data[8]  # Batch
                    Year = data[9]  # Year

                    # *** Logic to determine Shift based on current time ***
                    current_hour = current_datetime.hour
                    current_minute = current_datetime.minute

                    # FN Shift: 9:15 AM - 12:50 PM
                    if (current_hour == 9 and current_minute >= 15) or \
                            (current_hour > 9 and current_hour < 12) or \
                            (current_hour == 12 and current_minute <= 50):
                        Shift = "FN"
                    # AN Shift: 2:00 PM - 4:30 PM
                    elif (current_hour == 14 and current_minute >= 0) or \
                            (current_hour > 14 and current_hour < 16) or \
                            (current_hour == 16 and current_minute <= 30):
                        Shift = "AN"
                    else:
                        Shift = "Other"  # Or handle cases outside defined shifts as 'Absent', 'Invalid', etc.
                        # Consider how you want to handle times outside these specific shifts.
                        # For example, you might want to log it or not record attendance.

                    # ... (rest of your code, like check_attendance_query and insert_query) ...
                    # Check for existing attendance for the current date AND shift using parameterized query
                    check_attendance_query = """
                        SELECT * FROM attentb
                        WHERE Datetime LIKE %s AND Regno = %s AND Attendance = 'Present' AND Shift = %s
                        """
                    # Ensure you use the determined 'Shift' value here
                    db_cursor.execute(check_attendance_query, (current_date_str + '%', regno, Shift))

                    existing_data = db_cursor.fetchone()

                    if existing_data is None:

                        # Insert new attendance record using parameterized query

                        insert_query = """

                                            INSERT INTO attentb (Regno, Name, Mobile, Department, Batch, Year, Shift, Datetime, Attendance)

                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)

                                            """

                        # Pass current_datetime (datetime object) for Datetime column

                        insert_data = (regno, name, Mobile, Department, Batch, Year, Shift, current_datetime, 'Present')

                        db_cursor.execute(insert_query, insert_data)

                        db_conn.commit()  # Commit changes to the database

                        print("\n--- ATTENDANCE MARKED SUCCESSFULLY ---")

                        print(f"Student: {name} (RegNo: {regno})")

                        print(f"Shift: {Shift}")

                        print(f"Time: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

                        print("--------------------------------------\n")

                        db_conn.commit()

                        # Optional: Play a sound

                        winsound.Beep(1000, 300)  # Higher frequency, longer duration for attendance marked

                        print("Face Attendance Info Saved")

                        print(Mobile)

                        # sendmsg(Mobile,str(regno) +","+ str(name) +"is In College Today")

                        # --- ADD THESE TWO LINES HERE TO STOP AFTER SUCCESSFUL MARK ---

                        attendance_marked_and_stop = True

                        break  # This will exit the 'for face_id, tracker in trackers.items():' loop

                    else:

                        print("Already Face Attendance Info Saved for this Shift")

                        # You might also want to break here if only one attendance mark per click is desired

                        # attendance_marked_and_stop = True

                        # break
                else:
                    print('Incorrect username / password ! (No matching student found for:', ss, ')')

            except mysql.connector.Error as err:
                print(f"Database error during attendance check/save: {err}")
                db_conn.rollback()  # Rollback in case of error
            except Exception as e:  # Catch any other unexpected errors
                print(f"An unexpected error occurred in attendance processing: {e}")
        else:
            print("Database connection not established. Skipping attendance save.")


        if face_id in faces:
            tracker.draw(surfGr, gpath, face_id) # fsdkTracker.GetFacialFeatures(face_id)) # draw existing tracker
        else:
            missed.append(face_id)
    for mt in missed: # find and remove trackers that are not active anymore
        st = trackers[mt]
        if any(st.isIntersect(trackers[tr]) for tr in faces) or not st.draw(surfGr, gpath): del trackers[mt]

    if capturedFace not in trackers:
        capturedFace = None
        win.ShowWindow(inpBox, win.SW_HIDE)
    updateActiveFace()

    graphics.drawImage(backsurf, 0, 0) # show backsurface
    if sampleNum > 20: # This condition might be problematic for continuous operation
        break

    msg = win.MSG()
    if win.PeekMessage(win.byref(msg), 0, 0, 0, win.PM_REMOVE):
        win.TranslateMessage(win.byref(msg))
        win.DispatchMessage(win.byref(msg))
        if msg.message == win.WM_KEYDOWN and msg.wParam == win.VK_ESCAPE or need_to_exit:
            break

print("Please wait while saving Tracker memory... ", end='', flush=True)
fsdkTracker.SaveToFile(trackerMemoryFile)
win.ShowWindow(hwnd, win.SW_HIDE)

img.Free()
fsdkTracker.Free()
camera.Close()

FSDK.FinalizeCapturing()
FSDK.Finalize()

# --- Close database connection when the script finishes ---
if db_cursor:
    db_cursor.close()
if db_conn:
    db_conn.close()
print("Database connection closed.")