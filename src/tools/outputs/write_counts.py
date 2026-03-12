import os
import sqlite3
from openpyxl import load_workbook, Workbook

TRANSLATIONS = {
    "car": "Auto",
    "motorcycle": "Moto",
    "bus": "Bus",
    "truck": "Camion",
    "bicycle": "Bicicleta",
    "person": "Persona"
}

def write_counts_to_excel(video_folder: str, quarter_no: int, wb: Workbook, excel_report_path: str, total_typologies: list[str]) -> None:
    '''Writes vehicle counts from database to Excel report file.
    
    Args:
        wb (Workbook): The Excel workbook to write data into
        quarter_no (int): Quarter number for row positioning in Excel
    '''

    # Initialize dictionary to store turn information for each direction
    TURNS = {"N": [], "S": [], "E": [], "O": []}
    
    # Load the Excel workbook
    ws_inicio = wb["Inicio"]
    
    # Define cell ranges for each direction in the "Inicio" sheet
    turns_slices = {
        "N": "G12:G21",
        "S": "M12:M21",
        "E": "G24:G33",
        "O": "M24:M33"
    }

    # Extract turn information from the Excel sheet
    for direction, cell_range in turns_slices.items():
        for cell in ws_inicio[cell_range]:
            if cell[0].value is not None and cell[0].value != "":
                TURNS[direction].append(cell[0].value) #NOTE: Use to write in order

    # Connect to the SQLite database
    contes_db_path = os.path.join(video_folder, "Conteos.db")
    if not os.path.exists(contes_db_path):
        return print("Error: Conteos.db file not found in the video folder.")
    conn = sqlite3.connect(contes_db_path)
    cursor = conn.cursor()
    
    # Define vehicle types and initialize count dictionary
    vehicles_types = ["car", "motorcycle", "bus", "truck", "bicycle"]
    additional_typologies = total_typologies[5:] # NOTE: Only additional typologies and not considering pedestrians
    additional_typologies = [elem.lower() for elem in additional_typologies] # Lowercase.
    vehicles_types.extend(additional_typologies)
    # Create a set of all possible turns across all directions for initializing counts
    all_turns = set()
    for turns_list in TURNS.values():
        all_turns.update(turns_list)
    counts_by_type = {vehicle_type: {turn: 0 for turn in all_turns} for vehicle_type in vehicles_types}

    # No need to calculate time ranges since the database already contains only records for this specific quarter
    # The database in video_folder contains only records for the quarter specified by quarter_no
    
    # Query database for vehicle counts by type and turn
    # The database already contains only records for the specific quarter, so no additional time filtering is needed
    # First, let's query all relevant records at once to be more efficient
    cursor.execute("""
        SELECT vehicle_type, movement, COUNT(*)
        FROM VehicleCounts
        GROUP BY vehicle_type, movement
    """)
    
    results = cursor.fetchall()
    for vehicle_type, movement, count in results:
        if vehicle_type in counts_by_type and movement in counts_by_type[vehicle_type]:
            counts_by_type[vehicle_type][movement] = count

    # Close database connection
    conn.close()
    # Write counts to Excel file for each direction
    for direction in ["N", "S", "E", "O"]:
        ws = wb[direction]
        # Column structure:
        # The first 10 columns are for car
        # The next 10 columns are for bicycle (not used in current implementation)
        # The next 10 columns are for motorcycle
        # The next 10 columns are for bus
        # The next 10 columns are for truck
        row = quarter_no # Row 9 is for quarter 1
        for idx, vehicle_type in enumerate(vehicles_types):
            vehicle_type_counts = counts_by_type[vehicle_type]

            no_turn = 0
            # Iterate through turns in the order they appear in TURNS[direction] to maintain proper sequence
            for turn in TURNS[direction]:
                if turn in vehicle_type_counts:
                    count = vehicle_type_counts[turn]
                    start_col = 3+idx*10+no_turn # Column C and forward
                    ws.cell(
                        row=row,
                        column=start_col,
                        value=count
                    )
                    no_turn += 1

    # Save and close the workbook
    wb.save(excel_report_path)