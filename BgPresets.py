# Viewport Back — Presets
# Pretty list, JSON persistence, multi-delete, apply=single-select, delayed re-apply via timer
# Cinema 4D 2024/2025

import c4d, os, json
from c4d import gui, documents as docs, storage

IDC_TREE   = 1000
IDC_ADD    = 1001
IDC_DEL    = 1002
IDC_APPLY  = 1003

# --- enums <-> text ------------------------------------------------------------
_MODE_FROM_TXT  = {"Nearest": c4d.BASEDRAW_DATA_BACKIMAGEMODE_NEAREST,
                   "Linear":  c4d.BASEDRAW_DATA_BACKIMAGEMODE_LINEAR}
_MODE_TO_TXT    = {v:k for k,v in _MODE_FROM_TXT.items()}

_ALPHA_FROM_TXT = {"None":     c4d.BASEDRAW_ALPHA_NONE,
                   "Normal":   c4d.BASEDRAW_ALPHA_NORMAL,
                   "Inverted": c4d.BASEDRAW_ALPHA_INVERTED}
_ALPHA_TO_TXT   = {v:k for k,v in _ALPHA_FROM_TXT.items()}

# --- paths & JSON --------------------------------------------------------------
def _prefs_json_path():
    prefs = storage.GeGetC4DPath(c4d.C4D_PATH_PREFS)
    return os.path.join(prefs, "viewport_back_presets.json")

def _read_json():
    p = _prefs_json_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _write_json(items):
    try:
        with open(_prefs_json_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        gui.StatusSetText(f"Could not save presets: {e}")

# --- helpers -------------------------------------------------------------------
def _active_bd():
    d = docs.GetActiveDocument()
    return d.GetActiveBaseDraw() if d else None

def _safe_float(s):
    try: return float(s)
    except: return 0.0

def _transp_to_api(v):
    f = _safe_float(v)
    return f/100.0 if f > 1.0 else f

def _transp_to_txt(f):
    return f"{max(0.0, min(1.0, float(f)))*100.0:g}"

def _fmt_item_for_list(it):
    base = os.path.basename(it.get("image","")) or "(no image)"
    mode = it.get("mode","Linear")
    alpha= it.get("alpha","None")
    sx, sy = it.get("sizeX",0), it.get("sizeY",0)
    ox, oy = it.get("offX",0), it.get("offY",0)
    rot, tr = it.get("rot",0), it.get("transp",0)
    return f"{base} | {mode}/{alpha} | {sx:g}×{sy:g} | off={ox:g},{oy:g} | rot={rot:g}° | tr={tr}%"

# --- BaseDraw I/O --------------------------------------------------------------
def _grab_current_dict():
    bd = _active_bd()
    if not bd: return None
    return {
        "image": bd[c4d.BASEDRAW_DATA_PICTURE] or "",
        "mode":  _MODE_TO_TXT.get(bd[c4d.BASEDRAW_DATA_BACKIMAGEMODE], "Linear"),
        "keep":  1 if bd[c4d.BASEDRAW_DATA_KEEP_ASPECT] else 0,
        "offX":  float(bd[c4d.BASEDRAW_DATA_OFFSETX]),
        "offY":  float(bd[c4d.BASEDRAW_DATA_OFFSETY]),
        "rot":   float(bd[c4d.BASEDRAW_DATA_PICTURE_ROTATION]),
        "sizeX": float(bd[c4d.BASEDRAW_DATA_SIZEX]),
        "sizeY": float(bd[c4d.BASEDRAW_DATA_SIZEY]),
        "transp": _transp_to_txt(float(bd[c4d.BASEDRAW_DATA_PICTURE_TRANSPARENCY])),
        "alpha": _ALPHA_TO_TXT.get(bd[c4d.BASEDRAW_DATA_PICTURE_USEALPHA], "None")
    }

def _apply_once(it):
    """One application pass without the timer."""
    bd = _active_bd()
    if not bd:
        return False

    # temporarily detach aspect ratio so X/Y don't get locked together
    keep_saved = bool(it.get("keep", 1))
    bd[c4d.BASEDRAW_DATA_KEEP_ASPECT] = False

    bd[c4d.BASEDRAW_DATA_SHOWPICTURE]        = True
    bd[c4d.BASEDRAW_DATA_PICTURE]            = it.get("image","")
    bd[c4d.BASEDRAW_DATA_BACKIMAGEMODE]      = _MODE_FROM_TXT.get(it.get("mode","Linear"),
                                                                  c4d.BASEDRAW_DATA_BACKIMAGEMODE_LINEAR)
    bd[c4d.BASEDRAW_DATA_OFFSETX]            = float(it.get("offX",0))
    bd[c4d.BASEDRAW_DATA_OFFSETY]            = float(it.get("offY",0))
    bd[c4d.BASEDRAW_DATA_PICTURE_ROTATION]   = float(it.get("rot",0))
    bd[c4d.BASEDRAW_DATA_SIZEX]              = float(it.get("sizeX",0))
    bd[c4d.BASEDRAW_DATA_SIZEY]              = float(it.get("sizeY",0))
    bd[c4d.BASEDRAW_DATA_PICTURE_TRANSPARENCY]= _transp_to_api(it.get("transp", 0))
    bd[c4d.BASEDRAW_DATA_PICTURE_USEALPHA]   = _ALPHA_FROM_TXT.get(it.get("alpha","None"),
                                                                   c4d.BASEDRAW_ALPHA_NONE)

    # restore as it was
    bd[c4d.BASEDRAW_DATA_KEEP_ASPECT] = keep_saved
    c4d.EventAdd()
    return True

# --- Tree model ----------------------------------------------------------------
class PresetModel(gui.TreeViewFunctions):
    def __init__(self):
        self.items = []
        self.sel   = set()

    def GetFirst(self, root, userdata): return 0 if self.items else None
    def GetNext(self, root, userdata, obj):
        n = obj+1
        return n if n < len(self.items) else None
    def GetPred(self, root, userdata, obj): return obj-1 if obj > 0 else None
    def GetDown(self, root, userdata, obj): return None

    def GetName(self, root, userdata, obj):
        if 0 <= obj < len(self.items):
            return _fmt_item_for_list(self.items[obj])
        return ""
    def EmptyText(self, root, userdata):
        return "No presets added"

    def GetId(self, root, userdata, obj): return obj
    def IsSelected(self, root, userdata, obj): return obj in self.sel
    def Select(self, root, userdata, obj, mode):
        if mode == c4d.SELECTION_NEW: self.sel = {obj}
        elif mode == c4d.SELECTION_ADD: self.sel.add(obj)
        elif mode == c4d.SELECTION_SUB: self.sel.discard(obj)
        return True

# --- Dialog --------------------------------------------------------------------
class PresetDialog(gui.GeDialog):
    TIMER_DELAY_MS = 20  # delay before the second apply

    def __init__(self):
        super().__init__()
        self.model = PresetModel()
        self.tree  = None
        self.pending_apply = None  # preset dict to re-apply later
        self.timer_armed   = False

    def CreateLayout(self):
        self.SetTitle("Viewport Back — Presets")

        self.GroupBegin(10, c4d.BFH_LEFT, 3, 1)
        self.AddButton(IDC_ADD,   c4d.BFH_LEFT, name="Add")
        self.AddButton(IDC_DEL,   c4d.BFH_LEFT, name="Delete selected")
        self.AddButton(IDC_APPLY, c4d.BFH_LEFT, name="Apply to active Viewport")
        self.GroupEnd()

        self.GroupBegin(20, c4d.BFH_SCALEFIT|c4d.BFV_SCALEFIT, 1, 1)
        self.tree = self.AddCustomGui(IDC_TREE, c4d.CUSTOMGUI_TREEVIEW, "",
                                      c4d.BFH_SCALEFIT|c4d.BFV_SCALEFIT, 0, 0)
        self.GroupEnd()
        return True

    def InitValues(self):
        self.model.items = _read_json()

        layout = c4d.BaseContainer()
        layout.SetInt32(1, c4d.LV_TREE)
        self.tree.SetLayout(1, layout)
        self.tree.SetHeaderText(1, "Presets")
        self.tree.SetRoot(None, self.model, None)
        self.tree.Refresh()
        # just in case — timer disabled
        self.SetTimer(0)
        return True

    def _selected_indices(self):
        return sorted(self.model.sel)

    def _refresh(self, save=False):
        if self.tree: self.tree.Refresh()
        gui.GeUpdateUI()
        if save: _write_json(self.model.items)

    def Command(self, wid, msg):
        if wid == IDC_ADD:
            it = _grab_current_dict()
            if not it:
                gui.MessageDialog("No active viewport or unable to read settings.")
                return True
            self.model.items.append(it)
            self._refresh(save=True)
            return True

        if wid == IDC_DEL:
            sel = self._selected_indices()
            if not sel:
                gui.StatusSetText("No preset selected.")
                return True
            for idx in reversed(sel):
                if 0 <= idx < len(self.model.items):
                    self.model.items.pop(idx)
            self.model.sel = set()
            self._refresh(save=True)
            return True

        if wid == IDC_APPLY:
            sel = self._selected_indices()
            if len(sel) != 1:
                gui.StatusSetText("Select exactly one preset to apply.")
                return True

            item = self.model.items[sel[0]]

            # 1-й проход сейчас
            _apply_once(item)

            # prepare the "second apply" via timer
            self.pending_apply = dict(item)   # copy so the reference doesn’t change
            if not self.timer_armed:
                self.SetTimer(self.TIMER_DELAY_MS)  # Timer() will be called every X ms
                self.timer_armed = True
            return True

        return False

    def Timer(self, msg):
        """Called after TIMER_DELAY_MS following Apply — performs re-apply and disables the timer."""
        if not self.timer_armed:
            return

        if self.pending_apply:
            _apply_once(self.pending_apply)
            self.pending_apply = None

        # disable the timer so it doesn't tick constantly
        self.SetTimer(0)
        self.timer_armed = False

        # refresh viewport/GUI
        c4d.EventAdd()

# --- entry ---------------------------------------------------------------------
def main():
    global _DLG
    try: _DLG.Close()
    except Exception: pass
    _DLG = PresetDialog()
    _DLG.Open(c4d.DLG_TYPE_ASYNC, defaultw=900, defaulth=400)

if __name__ == "__main__":
    main()
