# ==============================================================================
# COPYRIGHT NOTICE
# ==============================================================================
# Project: Truss Analysis System (Tính toán ứng lực hệ giàn)
# Copyright (c) 2025 Nguyễn Mạnh Trường. All rights reserved.
#
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
#
# Written by Nguyễn Mạnh Trường, December 2025.
# ==============================================================================
import sys
import math
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QTabWidget, 
                             QMessageBox, QLineEdit, QSplitter, QComboBox, QStyledItemDelegate)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Circle

# --- Hỗ trợ đánh giá biểu thức toán học an toàn ---
def safe_eval(expr):
    if not expr: return 0.0
    try:
        allowed_names = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, 
                         "tan": math.tan, "pi": math.pi, "pow": math.pow, "abs": abs}
        code = compile(expr, "<string>", "eval")
        for name in code.co_names:
            if name not in allowed_names: raise NameError(f"Use of {name} is not allowed")
        return float(eval(code, {"__builtins__": {}}, allowed_names))
    except Exception: return 0.0

# --- Delegate để tự động viết hoa và chỉnh màu chữ khi nhập ---
class UpperCaseDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setStyleSheet("color: black; background-color: white;")
        return editor

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            text = index.model().data(index, Qt.ItemDataRole.EditRole)
            if text: editor.setText(str(text).upper())

    def setModelData(self, editor, model, index):
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text().upper(), Qt.ItemDataRole.EditRole)
        else: super().setModelData(editor, model, index)

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=6, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)
        self.axes.set_aspect('equal')

class TrussApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phần mềm Giàn Phẳng - Hỗ trợ Gối Nghiêng & Phân Tích Lực")
        self.setGeometry(50, 50, 1400, 850)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f6fa; }
            QLabel { color: #2c3e50; font-size: 11pt; font-weight: bold; }
            QLineEdit { 
                background-color: white; 
                color: black; 
                padding: 6px; border: 1px solid #bdc3c7; border-radius: 4px; 
            }
            QTableWidget { 
                background-color: white; 
                color: black; 
                gridline-color: #ecf0f1; 
                font-size: 10pt; 
                border: 1px solid #bdc3c7; 
            }
            QTableWidget QLineEdit { color: black; background-color: white; }
            QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; padding: 6px; font-weight: bold; border: 1px solid #bdc3c7; }
            QPushButton { background-color: #3498db; color: white; padding: 8px; font-weight: bold; border-radius: 4px; text-transform: uppercase; }
            QPushButton:hover { background-color: #2980b9; }
            QTabWidget::pane { border: 1px solid #bdc3c7; background: white; }
            QTabBar::tab { background: #ecf0f1; color: #2c3e50; padding: 8px 12px; margin-right: 2px; text-transform: uppercase; font-weight: bold; }
            QTabBar::tab:selected { background: white; color: #2980b9; border-bottom: 2px solid #3498db; }
            QComboBox { color: black; background-color: white; }
        """)

        self.timer = QTimer()
        self.timer.setInterval(800)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.plot_preview)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT PANEL ---
        left_panel = QWidget()
        left_vbox = QVBoxLayout(left_panel)
        
        cfg_frame = QWidget()
        cfg_layout = QHBoxLayout(cfg_frame)
        cfg_layout.setContentsMargins(0,0,0,0)
        self.inp_nodes = QLineEdit(); self.inp_nodes.setPlaceholderText("VD: 5")
        self.inp_bars = QLineEdit(); self.inp_bars.setPlaceholderText("VD: 7")
        btn_init = QPushButton("Tạo Bảng Mới")
        btn_init.clicked.connect(self.reset_tables)
        cfg_layout.addWidget(QLabel("Số Nút:"))
        cfg_layout.addWidget(self.inp_nodes)
        cfg_layout.addWidget(QLabel("Số Thanh:"))
        cfg_layout.addWidget(self.inp_bars)
        cfg_layout.addWidget(btn_init)
        left_vbox.addWidget(cfg_frame)

        self.tabs = QTabWidget()
        
        self.tb_nodes = QTableWidget()
        self.tb_nodes.setColumnCount(7) 
        self.tb_nodes.setHorizontalHeaderLabels(["ID Nút (Tên)", "X (m)", "Y (m)", "Fx (kN)", "Fy (kN)", "Gối Đỡ", "Góc Gối (độ)"])
        self.tb_nodes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.tb_nodes, "1. THÔNG SỐ NÚT")

        self.tb_bars = QTableWidget()
        self.tb_bars.setColumnCount(3)
        self.tb_bars.setHorizontalHeaderLabels(["ID Thanh", "Nút Đầu", "Nút Cuối"])
        self.tb_bars.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.tb_bars, "2. LIÊN KẾT THANH")
        
        upper_delegate = UpperCaseDelegate(self.tb_bars)
        self.tb_bars.setItemDelegateForColumn(1, upper_delegate)
        self.tb_bars.setItemDelegateForColumn(2, upper_delegate)
        
        left_vbox.addWidget(self.tabs)

        action_layout = QHBoxLayout()
        btn_plot = QPushButton("CẬP NHẬT HÌNH")
        btn_plot.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; font-size: 11pt;")
        btn_plot.setFixedHeight(45)
        btn_plot.clicked.connect(self.plot_preview)
        
        btn_calc = QPushButton("TÍNH TOÁN")
        btn_calc.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 11pt;")
        btn_calc.setFixedHeight(45)
        btn_calc.clicked.connect(self.calculate)
        
        action_layout.addWidget(btn_plot)
        action_layout.addWidget(btn_calc)
        left_vbox.addLayout(action_layout)

        self.res_tabs = QTabWidget()
        self.tb_res = QTableWidget()
        self.tb_res.setColumnCount(3)
        self.tb_res.setHorizontalHeaderLabels(["Đối Tượng", "Giá Trị (kN)", "Trạng Thái / Thành Phần"])
        self.tb_res.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.res_tabs.addTab(self.tb_res, "Kết Quả")

        self.tb_check = QTableWidget()
        self.tb_check.setColumnCount(4)
        self.tb_check.setHorizontalHeaderLabels(["Thanh/Gối", "Nút", "Góc (độ)", "Hệ Số (Cos/Sin)"])
        self.tb_check.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.res_tabs.addTab(self.tb_check, "Ma Trận A")
        left_vbox.addWidget(self.res_tabs)

        right_panel = QWidget()
        right_vbox = QVBoxLayout(right_panel)
        right_vbox.addStretch(1)
        self.canvas = MplCanvas(self)
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.addWidget(QLabel("MÔ HÌNH HÌNH HỌC (Dựa trên Tọa độ X, Y)"))
        canvas_layout.addWidget(self.canvas)
        right_vbox.addWidget(canvas_container)
        right_vbox.addStretch(1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([650, 750])
        layout.addWidget(splitter)

        self.reset_tables()

    def reset_tables(self):
        try:
            txt_nodes = self.inp_nodes.text().strip() or "5"
            txt_bars = self.inp_bars.text().strip() or "7"
            n_nodes, n_bars = int(txt_nodes), int(txt_bars)
            
            self.tb_nodes.setRowCount(n_nodes)
            for i in range(n_nodes):
                node_name = chr(65 + i) if i < 26 else f"N{i+1}"
                item_name = QTableWidgetItem(node_name)
                item_name.setForeground(QColor("black"))
                self.tb_nodes.setItem(i, 0, item_name)
                
                for j in range(1, 5): 
                    item = QTableWidgetItem("0")
                    item.setForeground(QColor("black"))
                    self.tb_nodes.setItem(i, j, item)
                
                cb = QComboBox()
                cb.addItems(["-", "Gối Cố Định", "Gối Di Động"])
                cb.currentTextChanged.connect(self.schedule_update)
                self.tb_nodes.setCellWidget(i, 5, cb)
                
                item_angle = QTableWidgetItem("0")
                item_angle.setToolTip("Góc của mặt phẳng lăn (0=Ngang -> Phản lực đứng)")
                item_angle.setForeground(QColor("black"))
                self.tb_nodes.setItem(i, 6, item_angle)

            self.tb_bars.setRowCount(n_bars)
            for i in range(n_bars):
                item_id = QTableWidgetItem(str(i+1))
                item_id.setForeground(QColor("black"))
                self.tb_bars.setItem(i, 0, item_id)
                
                item_u = QTableWidgetItem("")
                item_u.setForeground(QColor("black"))
                self.tb_bars.setItem(i, 1, item_u)
                
                item_v = QTableWidgetItem("")
                item_v.setForeground(QColor("black"))
                self.tb_bars.setItem(i, 2, item_v)

            try:
                self.tb_nodes.itemChanged.disconnect()
                self.tb_bars.itemChanged.disconnect()
            except: pass
            self.tb_nodes.itemChanged.connect(self.schedule_update)
            self.tb_bars.itemChanged.connect(self.schedule_update)
            self.plot_preview()
        except ValueError:
            QMessageBox.warning(self, "Lỗi", "Số lượng phải là số nguyên!")

    def schedule_update(self):
        self.timer.start()

    def get_input_data(self):
        nodes = {}
        bars = []
        try:
            for r in range(self.tb_nodes.rowCount()):
                nid_item = self.tb_nodes.item(r, 0)
                if not nid_item: continue
                nid = nid_item.text().strip()
                if not nid: continue
                
                x_val = safe_eval(self.tb_nodes.item(r, 1).text())
                y_val = safe_eval(self.tb_nodes.item(r, 2).text())
                fx_val = safe_eval(self.tb_nodes.item(r, 3).text())
                fy_val = safe_eval(self.tb_nodes.item(r, 4).text())
                angle_supp_val = safe_eval(self.tb_nodes.item(r, 6).text())
                
                cb = self.tb_nodes.cellWidget(r, 5)
                supp = cb.currentText() if cb else "-"
                
                nodes[nid] = {'x': x_val, 'y': y_val, 'fx': fx_val, 'fy': fy_val, 's': supp, 's_angle': angle_supp_val}

            for r in range(self.tb_bars.rowCount()):
                bid = self.tb_bars.item(r, 0).text()
                u_item = self.tb_bars.item(r, 1)
                v_item = self.tb_bars.item(r, 2)
                
                if not (u_item and v_item): continue
                u_name = u_item.text().strip().upper()
                v_name = v_item.text().strip().upper()
                
                if not (u_name and v_name): continue
                if u_name not in nodes: nodes[u_name] = {'x':0,'y':0, 'fx':0,'fy':0,'s':'-', 's_angle': 0}
                if v_name not in nodes: nodes[v_name] = {'x':0,'y':0, 'fx':0,'fy':0,'s':'-', 's_angle': 0}

                bars.append({'id': bid, 'u': u_name, 'v': v_name})
        except: return None, None
        if not nodes: return None, None
        return nodes, bars

    def plot_preview(self):
        self.plot_structure(None, None)

    def plot_structure(self, S_forces, R_forces):
        nodes, bars = self.get_input_data()
        self.canvas.axes.clear()
        self.canvas.axes.grid(True, linestyle=':', alpha=0.6)
        self.canvas.axes.set_title("Sơ Đồ Kết Cấu & Biểu Đồ Lực")

        if not nodes:
            self.canvas.draw()
            return

        xs = [n['x'] for n in nodes.values()]
        ys = [n['y'] for n in nodes.values()]
        if xs and ys:
            margin = max(1.5, (max(xs)-min(xs))*0.1)
            self.canvas.axes.set_xlim(min(xs)-margin, max(xs)+margin)
            self.canvas.axes.set_ylim(min(ys)-margin, max(ys)+margin)

        max_force = 1.0
        if S_forces is not None:
            vals = np.abs(S_forces)
            if len(vals) > 0: max_force = np.max(vals)
            if max_force == 0: max_force = 1.0

        for i, b in enumerate(bars):
            if b['u'] in nodes and b['v'] in nodes:
                p1 = nodes[b['u']]
                p2 = nodes[b['v']]
                color = 'black'
                width = 2
                label_txt = f"[{b['id']}]"
                
                if S_forces is not None and i < len(S_forces):
                    val = S_forces[i]
                    if val > 1e-4: 
                        color = '#2980b9' 
                        label_txt = f"{val:.2f}"
                    elif val < -1e-4: 
                        color = '#c0392b' 
                        label_txt = f"{val:.2f}"
                    else:
                        color = '#95a5a6'
                        label_txt = "0"
                    width = 1 + (abs(val)/max_force)*4 

                self.canvas.axes.plot([p1['x'], p2['x']], [p1['y'], p2['y']], 
                                      color=color, linewidth=width, marker='o', markersize=4, zorder=1)
                mx, my = (p1['x']+p2['x'])/2, (p1['y']+p2['y'])/2
                self.canvas.axes.text(mx, my, label_txt, color=color, fontsize=9, fontweight='bold',
                                      bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1))

        for nid, n in nodes.items():
            x, y = n['x'], n['y']
            s_angle = n['s_angle'] 
            
            self.canvas.axes.plot(x, y, 'ko', markersize=6, zorder=5)
            self.canvas.axes.text(x, y+0.25, str(nid), fontweight='bold', fontsize=10, ha='center',
                                  bbox=dict(facecolor='white', edgecolor='none', alpha=0.6, pad=0.5), zorder=6)
            
            if n['s'] != "-":
                tr = matplotlib.transforms.Affine2D().rotate_deg_around(x, y, s_angle) + self.canvas.axes.transData
                
                if n['s'] == "Gối Cố Định":
                    p = Polygon([(x, y), (x-0.2, y-0.35), (x+0.2, y-0.35)], closed=True, 
                                facecolor='white', edgecolor='black', transform=tr, zorder=4)
                    self.canvas.axes.add_patch(p)
                    line_ground = matplotlib.lines.Line2D([x-0.3, x+0.3], [y-0.35, y-0.35], color='black', transform=tr)
                    self.canvas.axes.add_line(line_ground)
                    
                elif n['s'] == "Gối Di Động":
                    c = Circle((x, y-0.15), 0.15, facecolor='white', edgecolor='black', transform=tr, zorder=4)
                    self.canvas.axes.add_patch(c)
                    line_ground = matplotlib.lines.Line2D([x-0.3, x+0.3], [y-0.3, y-0.3], color='black', transform=tr)
                    self.canvas.axes.add_line(line_ground)

            if abs(n['fx']) > 0 or abs(n['fy']) > 0:
                scale = 0.5
                mag = math.sqrt(n['fx']**2 + n['fy']**2)
                if mag > 0:
                    dx = (n['fx'] / mag) * scale
                    dy = (n['fy'] / mag) * scale
                    self.canvas.axes.arrow(x, y, dx, dy, head_width=0.15, head_length=0.2, 
                                           fc='#27ae60', ec='#27ae60', zorder=6)
                    self.canvas.axes.text(x+dx*1.2, y+dy*1.2, "F", color='#27ae60', fontsize=9, fontweight='bold')

        self.canvas.draw()

    def calculate(self):
        nodes, bars = self.get_input_data()
        if not nodes or not bars: return

        n_nodes = len(nodes)
        n_bars = len(bars)
        
        reaction_map = [] 
        node_keys = sorted(nodes.keys())
        map_idx = {nid: i for i, nid in enumerate(node_keys)} 

        for nid in node_keys:
            s_type = nodes[nid]['s']
            s_angle = nodes[nid]['s_angle']
            idx = map_idx[nid]
            
            if s_type == "Gối Cố Định":
                reaction_map.append((idx, 'x', f"Ax_{nid}", 0)) 
                reaction_map.append((idx, 'y', f"Ay_{nid}", 90))
                
            elif s_type == "Gối Di Động":
                reaction_angle = s_angle + 90
                reaction_map.append((idx, 'custom', f"R_{nid}", reaction_angle))

        n_reactions = len(reaction_map)
        n_unknowns = n_bars + n_reactions 
        n_equations = 2 * n_nodes         
        
        A = np.zeros((n_equations, n_unknowns))
        F_vec = np.zeros(n_equations)
        debug_info = [] 

        for nid, n in nodes.items():
            idx = map_idx[nid]
            F_vec[2*idx]   = -n['fx'] 
            F_vec[2*idx+1] = -n['fy'] 

        for j, b in enumerate(bars):
            u, v = b['u'], b['v']
            p1, p2 = nodes[u], nodes[v]
            
            dx = p2['x'] - p1['x']
            dy = p2['y'] - p1['y']
            L = math.sqrt(dx**2 + dy**2)
            
            if L < 1e-6:
                QMessageBox.critical(self, "Lỗi", f"Thanh {b['id']} có chiều dài ~ 0!")
                return

            c = dx / L
            s = dy / L
            angle_deg = math.degrees(math.atan2(dy, dx))
            
            idx_u = map_idx[u]
            idx_v = map_idx[v]

            A[2*idx_u, j]   = c
            A[2*idx_u+1, j] = s
            debug_info.append((f"Thanh {b['id']}", u, f"{angle_deg:.1f}", f"C:{c:.2f} S:{s:.2f}"))

            A[2*idx_v, j]   = -c
            A[2*idx_v+1, j] = -s
            ang_v = angle_deg + 180
            if ang_v > 180: ang_v -= 360
            debug_info.append((f"Thanh {b['id']}", v, f"{ang_v:.1f}", f"C:{-c:.2f} S:{-s:.2f}"))

        for k, (node_idx, r_type, label, r_angle) in enumerate(reaction_map):
            col_idx = n_bars + k
            rad_r = math.radians(r_angle)
            cos_r = math.cos(rad_r)
            sin_r = math.sin(rad_r)
            
            A[2*node_idx, col_idx] = cos_r
            A[2*node_idx+1, col_idx] = sin_r
            debug_info.append((f"Gối {label}", node_keys[node_idx], f"{r_angle:.1f}", f"Cx:{cos_r:.2f} Sy:{sin_r:.2f}"))

        try:
            X, residuals, rank, s_val = np.linalg.lstsq(A, F_vec, rcond=None)
            S_results = X[:n_bars]      
            R_results = X[n_bars:]      
            
            self.display_results(S_results, bars, R_results, reaction_map)
            self.display_check_matrix(debug_info)
            self.plot_structure(S_results, R_results)
            QMessageBox.information(self, "Thành Công", "Đã tính toán xong!\nXem chi tiết ở Tab Kết Quả.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi Toán Học", f"Không giải được hệ phương trình:\n{str(e)}")

    def display_results(self, S, bars, R, r_map):
        self.tb_res.setRowCount(0)
        row_count = 0
        for i, val in enumerate(S):
            self.tb_res.insertRow(row_count)
            self.tb_res.setItem(row_count, 0, QTableWidgetItem(f"Thanh {bars[i]['id']}"))
            self.tb_res.setItem(row_count, 1, QTableWidgetItem(f"{abs(val):.3f}"))
            if val > 1e-4: st = "KÉO (+)"; col = "#2980b9" 
            elif val < -1e-4: st = "NÉN (-)"; col = "#c0392b" 
            else: st = "Không Lực"; col = "black"
            it = QTableWidgetItem(st); it.setForeground(QColor(col)); it.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.tb_res.setItem(row_count, 2, it)
            row_count += 1
            
        for i, val in enumerate(R):
            self.tb_res.insertRow(row_count)
            label = r_map[i][2]
            
            # Hiển thị Tổng phản lực
            self.tb_res.setItem(row_count, 0, QTableWidgetItem(f"P.Lực {label} (Tổng)"))
            self.tb_res.setItem(row_count, 1, QTableWidgetItem(f"{abs(val):.3f}"))
            
            # Hiển thị thành phần chiếu (Rx, Ry) 
            r_angle = r_map[i][3]
            rad = math.radians(r_angle)
            rx = val * math.cos(rad)
            ry = val * math.sin(rad)
            
            detail_str = f"Rx={rx:.1f}, Ry={ry:.1f}"
            self.tb_res.setItem(row_count, 2, QTableWidgetItem(detail_str))
            row_count += 1

    def display_check_matrix(self, data):
        self.tb_check.setRowCount(len(data))
        for i, row in enumerate(data):
            self.tb_check.setItem(i, 0, QTableWidgetItem(str(row[0]))) 
            self.tb_check.setItem(i, 1, QTableWidgetItem(str(row[1]))) 
            self.tb_check.setItem(i, 2, QTableWidgetItem(str(row[2]))) 
            self.tb_check.setItem(i, 3, QTableWidgetItem(str(row[3]))) 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TrussApp()
    window.show()
    sys.exit(app.exec())


