import mysql.connector
import pandas as pd
from datetime import datetime, timedelta

# Attempt to connect to DB right away so we fail immediately if something is wrong.
# hope I typed the creds right...
try:
    conn = mysql.connector.connect(
        user='mhaapala',
        password='365-fall24-028148594',
        host='mysql.labthreesixfive.com',
        database='mhaapala'
    )
except mysql.connector.Error as err:
    # If something goes wrong, we print the error and quit
    print("Oh no, DB connection failed!")
    print(f"Error details: {err}")
    exit()


def main():
    print("Braeden Alonge, Miro Haapalainen - Lab 7 (hopefully working!)")
    while True:
        # Just show menu and hope user picks something valid...
        print("\nPlease choose an action:")
        print("1. Rooms and Rates")
        print("2. Reservations")
        print("3. Reservation Cancellation")
        print("4. Detailed Reservation Information")
        print("5. Revenue")
        cmd = input("Type a number or 'exit': ").strip()

        if cmd == "1":
            show_rooms_and_rates()
        elif cmd == "2":
            handle_reservations()
        elif cmd == "3":
            cancel_reservation()
        elif cmd == "4":
            detailed_reservations()
        elif cmd == "5":
            show_revenue()
        elif cmd.lower() == "exit":
            print("Bye! Take care!")
            break
        else:
            # Oops user typed something random again
            print("Not a valid option, try again.")


def show_rooms_and_rates():
    """
    FR1: Display rooms with popularity, next available check-in, and info about the last stay.
    This is basically a complicated SQL query with left joins.
    Let's hope I typed it right...
    """
    try:
        q = """
            SELECT
                r.RoomCode,
                r.RoomName,
                r.Beds,
                r.bedType,
                r.maxOcc,
                r.basePrice,
                r.decor,
                COALESCE(rp.PopularityScore, 0.00) AS PopularityScore,
                COALESCE(nac.NextAvailableCheckIn, CURRENT_DATE) AS NextAvailableCheckIn,
                COALESCE(ms.LengthOfStay, 0) AS LastStayLength,
                COALESCE(ms.LastCheckout, 'N/A') AS LastCheckout
            FROM lab7_rooms r
            LEFT JOIN (
                SELECT Room, 
                    ROUND(
                      SUM(
                        DATEDIFF(LEAST(Checkout, CURRENT_DATE),
                                 GREATEST(CheckIn, DATE_SUB(CURRENT_DATE, INTERVAL 180 DAY)))
                      ) / 180,
                      2
                    ) AS PopularityScore
                FROM lab7_reservations
                WHERE CheckIn <= CURRENT_DATE
                  AND Checkout >= DATE_SUB(CURRENT_DATE, INTERVAL 180 DAY)
                GROUP BY Room
            ) rp ON r.RoomCode = rp.Room
            LEFT JOIN (
                SELECT Room, DATE_ADD(MAX(Checkout), INTERVAL 1 DAY) AS NextAvailableCheckIn
                FROM lab7_reservations
                WHERE Checkout <= CURRENT_DATE
                GROUP BY Room
            ) nac ON r.RoomCode = nac.Room
            LEFT JOIN (
                SELECT Room,
                       DATEDIFF(MAX(Checkout), MIN(CheckIn)) AS LengthOfStay,
                       MAX(Checkout) AS LastCheckout
                FROM lab7_reservations
                WHERE Checkout < CURRENT_DATE
                GROUP BY Room
            ) ms ON r.RoomCode = ms.Room
            ORDER BY PopularityScore DESC;
        """
        dataf = pd.read_sql(q, conn)
        print("\n--- Rooms and Rates ---")
        print(dataf.to_string(index=False))
    except Exception as e:
        # If something happens, we print it out and move on
        print("Ouch, couldn't retrieve room data.")
        print(e)


def handle_reservations():
    """
    FR2: Reservations
    This requires a bunch of user input, searching for available rooms, etc.
    Let's hope user doesn't type nonsense...
    """
    try:
        fname = input("First Name: ").strip()
        lname = input("Last Name: ").strip()
        rm_pref = input("Room Code (or 'Any'): ").strip()
        bed_pref = input("Bed Type (or 'Any'): ").strip()
        start_date = input("Start Date (YYYY-MM-DD): ").strip()
        end_date = input("End Date (YYYY-MM-DD): ").strip()
        adults = int(input("Number of Adults: "))
        kids = int(input("Number of Children: "))
        guests = adults + kids

        # Validate date input, just a tiny bit :D :
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if end_dt <= start_dt:
                print("End date must be after start date.")
                return
        except ValueError:
            print("Date format error, please use YYYY-MM-DD")
            return

        # Construct query
        # We'll use parameterized queries to avoid injection.
        # If 'Any', we won't add that filter
        params = []
        query_filters = ["r.maxOcc >= %s"]
        params.append(guests)

        if rm_pref.lower() != "any":
            query_filters.append("r.RoomCode = %s")
            params.append(rm_pref)

        if bed_pref.lower() != "any":
            query_filters.append("r.bedType = %s")
            params.append(bed_pref)

        # For availability: no overlapping reservation
        # We'll just ensure no reservation overlaps the given date range
        # i.e. NOT EXISTS a reservation with overlapping date range
        q_base = f"""
            SELECT r.RoomCode, r.RoomName, r.bedType, r.basePrice, r.maxOcc
            FROM lab7_rooms r
            WHERE {" AND ".join(query_filters)}
              AND NOT EXISTS (
                  SELECT 1 FROM lab7_reservations res
                  WHERE res.Room = r.RoomCode
                    AND res.CheckIn < %s
                    AND res.Checkout > %s
              )
        """
        # Add the date params at the end
        params.append(end_date)
        params.append(start_date)

        df = pd.read_sql(q_base, conn, params=params)

        if df.empty:
            # No exact match. Suggest alternatives
            print("No exact matches found. Let's suggest some alternatives:")
            alt_query = """
                SELECT r.RoomCode, r.RoomName, r.bedType, r.basePrice, r.maxOcc
                FROM lab7_rooms r
                WHERE r.maxOcc >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM lab7_reservations rr
                      WHERE rr.Room = r.RoomCode
                        AND rr.CheckIn < DATE_ADD(%s, INTERVAL 1 DAY)
                        AND rr.Checkout > DATE_SUB(%s, INTERVAL 1 DAY)
                  )
                LIMIT 5
            """
            alt_suggestions = pd.read_sql(alt_query, conn, params=(guests, end_date, start_date))
            if alt_suggestions.empty:
                print("No suitable rooms found at all. Sorry!")
                return
            else:
                print("Possible Suggestions:")
                print(alt_suggestions.to_string(index=False))
                chosen_code = input("Type a RoomCode from these suggestions to book, or 'cancel': ").strip()
                if chosen_code.lower() == 'cancel':
                    print("Reservation request aborted.")
                    return
                chosen_room = alt_suggestions[alt_suggestions['RoomCode'] == chosen_code]
                if chosen_room.empty:
                    print("Invalid choice.")
                    return
                else:
                    insert_reservation(fname, lname, chosen_code,
                                       chosen_room['RoomName'].iloc[0],
                                       chosen_room['bedType'].iloc[0],
                                       start_date, end_date, adults, kids,
                                       chosen_room['basePrice'].iloc[0])
        else:
            print("Available Rooms:")
            print(df.to_string(index=False))
            chosen_code = input("Enter the RoomCode to book, or 'cancel': ").strip()
            if chosen_code.lower() == "cancel":
                print("Canceled.")
                return
            chosen_df = df[df['RoomCode'] == chosen_code]
            if chosen_df.empty:
                print("No room with that code from the list.")
                return
            insert_reservation(fname, lname, chosen_code,
                               chosen_df['RoomName'].iloc[0],
                               chosen_df['bedType'].iloc[0],
                               start_date, end_date, adults, kids,
                               chosen_df['basePrice'].iloc[0])

    except Exception as e:
        print("Oops, something went wrong in reservations.")
        print(e)


def insert_reservation(fname, lname, room_code, room_name, bed_type, start_date, end_date, adults, kids, base_price):
    """
    Insert a new reservation and show confirmation.
    FR2 requires cost calculation with weekend markup on Sat/Sun.
    Let's do a daily loop. Sigh...
    """
    sd = datetime.strptime(start_date, "%Y-%m-%d")
    ed = datetime.strptime(end_date, "%Y-%m-%d")
    nights = (ed - sd).days
    total_cost = 0.0
    for i in range(nights):
        day = sd + timedelta(days=i)
        w = day.weekday()
        # weekend: Saturday(5), Sunday(6)
        if w == 5 or w == 6:
            total_cost += float(base_price) * 1.10
        else:
            total_cost += float(base_price)

    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(CODE),0)+1 FROM lab7_reservations")
    new_code = cur.fetchone()[0]

    ins_q = """
        INSERT INTO lab7_reservations (CODE, Room, CheckIn, Checkout, Rate, LastName, FirstName, Adults, Kids)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cur.execute(ins_q, (new_code, room_code, start_date, end_date, base_price, lname, fname, adults, kids))
    conn.commit()
    cur.close()

    print("\n--- Reservation Confirmed ---")
    print(f"Reservation Code: {new_code}")
    print(f"Name: {fname} {lname}")
    print(f"Room: {room_code} - {room_name}")
    print(f"Bed Type: {bed_type}")
    print(f"Check-In: {start_date}")
    print(f"Check-Out: {end_date}")
    print(f"Adults: {adults}, Children: {kids}")
    print(f"Total Cost: ${round(total_cost)}")


def cancel_reservation():
    """
    FR3: Cancel existing reservation.
    Just ask code, show details, confirm, delete.
    """
    try:
        code = input("Enter reservation code to cancel: ").strip()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM lab7_reservations WHERE CODE = %s", (code,))
        r = cur.fetchone()
        if not r:
            print("No reservation with that code.")
            cur.close()
            return

        print("\nReservation Details:")
        print(f"Code: {r['CODE']}")
        print(f"Guest: {r['FirstName']} {r['LastName']}")
        print(f"Room: {r['Room']}")
        print(f"CheckIn: {r['CheckIn']} Checkout: {r['Checkout']}")

        confirm = input("Type 'yes' to confirm cancellation: ").strip().lower()
        if confirm != 'yes':
            print("Not canceled.")
            cur.close()
            return

        cur.execute("DELETE FROM lab7_reservations WHERE CODE = %s", (code,))
        conn.commit()
        print("Reservation canceled.")
        cur.close()

    except Exception as e:
        print("Problem canceling reservation.")
        print(e)


def detailed_reservations():
    """
    FR4: Detailed reservation info with flexible search.
    We'll do partial matches with LIKE.
    If blank, no filter applied.
    We'll be careful about date parsing.
    """
    try:
        cur = conn.cursor(dictionary=True)
        first = input("First name (blank=any): ").strip()
        last = input("Last name (blank=any): ").strip()
        rcode = input("Room code (blank=any): ").strip()
        rescode = input("Reservation code (blank=any): ").strip()
        dfrom = input("Start date (YYYY-MM-DD or blank): ").strip()
        dto = input("End date (YYYY-MM-DD or blank): ").strip()

        q = """
            SELECT r.CODE, r.Room, r.CheckIn, r.Checkout, r.Rate, r.LastName, r.FirstName,
                   r.Adults, r.Kids, rm.RoomName, rm.Beds, rm.BedType, rm.maxOcc, rm.basePrice, rm.decor
            FROM lab7_reservations r
            JOIN lab7_rooms rm ON r.Room = rm.RoomCode
            WHERE 1=1
        """
        p = []
        if first:
            q += " AND r.FirstName LIKE %s"
            p.append(f"%{first}%")
        if last:
            q += " AND r.LastName LIKE %s"
            p.append(f"%{last}%")
        if rcode:
            q += " AND r.Room LIKE %s"
            p.append(f"%{rcode}%")
        if rescode:
            # exact match on code
            q += " AND r.CODE = %s"
            p.append(rescode)

        if dfrom:
            try:
                datetime.strptime(dfrom, "%Y-%m-%d")
                q += " AND r.CheckIn >= %s"
                p.append(dfrom)
            except ValueError:
                print("Invalid start date format. Skipping that filter.")

        if dto:
            try:
                datetime.strptime(dto, "%Y-%m-%d")
                q += " AND r.Checkout <= %s"
                p.append(dto)
            except ValueError:
                print("Invalid end date format. Skipping that filter.")

        cur.execute(q, tuple(p))
        results = cur.fetchall()

        if results:
            print("\nReservations Found:")
            for row in results:
                # Just print everything in a nice format
                print(f"""
Reservation Code: {row['CODE']}
Room: {row['Room']} ({row['RoomName']})
Check-in: {row['CheckIn']}
Check-out: {row['Checkout']}
Rate: {row['Rate']}
Name: {row['FirstName']} {row['LastName']}
Adults: {row['Adults']}, Kids: {row['Kids']}
Beds: {row['Beds']}
Bed Type: {row['BedType']}
Max Occ: {row['maxOcc']}
Base Price: {row['basePrice']}
Decor: {row['decor']}
                """)
        else:
            print("No matches found.")

        cur.close()
    except Exception as e:
        print("Something went wrong in detailed_reservations.")
        print(e)


def show_revenue():
    """
    FR5: Show month-by-month revenue.
    Consider weekends (Sat=5, Sun=6) as 110% rate.
    We'll break down each reservation by nights, summing up daily revenue.
    """
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT YEAR(CURDATE()) AS current_year;")
        cy = cur.fetchone()['current_year']

        cur.execute("SELECT RoomCode, basePrice FROM lab7_rooms;")
        rms = cur.fetchall()
        rev_data = {r['RoomCode']: {m:0.0 for m in range(1,13)} for r in rms}

        ystart = f"{cy}-01-01"
        nyear = f"{cy+1}-01-01"

        qres = """
            SELECT r.RoomCode, res.CheckIn, res.Checkout, r.basePrice
            FROM lab7_reservations res
            JOIN lab7_rooms r ON r.RoomCode = res.Room
            WHERE NOT (res.Checkout <= %s OR res.CheckIn >= %s)
            ORDER BY r.RoomCode;
        """
        cur.execute(qres, (ystart, nyear))
        reservations = cur.fetchall()

        # Calculate revenue per night
        for rv in reservations:
            rc = rv['RoomCode']
            bp = rv['basePrice']
            ci = rv['CheckIn']
            co = rv['Checkout']
            total_nights = (co - ci).days
            for i in range(total_nights):
                nd = ci + timedelta(days=i)
                if nd.year == cy:
                    wd = nd.weekday()
                    if wd == 5 or wd == 6:
                        daily = float(bp)*1.10
                    else:
                        daily = float(bp)
                    rev_data[rc][nd.month] += daily

        print("\n--- Revenue Report ---")
        print(f"Year: {cy}")
        header = "RoomCode | " + " | ".join([f"{m:>5s}" for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]]) + " | Total"
        print(header)
        print("-"*len(header)*2) # maybe a bit long line...

        totals = {m:0 for m in range(1,13)}

        for rcd in rev_data:
            vals = rev_data[rcd]
            rounded_vals = [round(vals[m]) for m in range(1,13)]
            rtotal = sum(rounded_vals)
            for m in range(1,13):
                totals[m] += rounded_vals[m-1]
            line = f"{rcd:8s} | " + " | ".join(f"{x:5d}" for x in rounded_vals) + f" | {rtotal:5d}"
            print(line)

        grand_total = sum(totals[m] for m in range(1,13))
        print("-"*len(header)*2)
        total_line = "Totals   | " + " | ".join(f"{totals[m]:5d}" for m in range(1,13)) + f" | {grand_total:5d}"
        print(total_line)

        cur.close()

    except Exception as e:
        print("Revenue generation error.")
        print(e)


if __name__ == "__main__":
    main()
