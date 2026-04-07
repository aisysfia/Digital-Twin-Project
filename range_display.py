import omni.ui as ui
from omni.kit.scripting import BehaviorScript

class TelemetryDashboard(BehaviorScript):
    def on_init(self):
        self.ranges = []
        # IMPORTANT: Update this to the exact path of your predicted_range.txt file
        filepath = r"C:\path\to\your\predicted_range.txt" 
        
        try:
            with open(filepath, "r") as f:
                self.ranges = [line.strip() for line in f.readlines()]
            print(f"Loaded {len(self.ranges)} predictions.")
        except Exception as e:
            print(f"Could not load range data: {e}")
            
        # Create a floating UI panel in the Omniverse workspace
        self.window = ui.Window("EV Telemetry Dashboard", width=300, height=100)
        
        with self.window.frame:
            with ui.VStack(padding=15, spacing=8):
                ui.Label("Digital Twin Status", style={"font_size": 20, "color": 0xFF00AFFF})
                self.range_label = ui.Label("Predicted Range: -- km", style={"font_size": 18})

    def on_update(self, current_time: float, delta_time: float):
        # Safety check to ensure data and UI exist
        if not self.ranges or not hasattr(self, 'range_label'):
            return
            
        # Map Omniverse timeline seconds to your data rows
        index = int(current_time) 
        if index < len(self.ranges):
            current_range = self.ranges[index]
            self.range_label.text = f"Predicted Range: {current_range} km"

    def on_destroy(self):
        # Clean up the UI window if you delete the script or close the stage
        if self.window:
            self.window.visible = False
            self.window = None