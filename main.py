"""
Τζόκερ · Λόττο · ΚΙΝΟ – αποτελέσματα, έλεγχος δελτίων με ποσά κερδών, αριθμοί με στατιστικά.
"""
import threading
import time
import webbrowser

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.stacklayout import StackLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

import lottery as L
import scanner as SC
import tickets as T
import ui_widgets as UW

IS_ANDROID = platform == "android"
TABS = ("home", "numbers", "check", "tickets")
TITLES = {"home": "Τζόκερ · Λόττο · ΚΙΝΟ", "numbers": "Οι αριθμοί μου", "check": "Έλεγχος δελτίου",
          "tickets": "Τα δελτία μου"}
GCOL = {"joker": (0.84, 0.16, 0.25, 1), "lotto": (0.16, 0.42, 0.85, 1), "kino": (0.95, 0.6, 0.05, 1)}
JOKER_BALL = (0.96, 0.75, 0.1, 1)

KV = """
#:import dp kivy.metrics.dp

<NavItem>:
    orientation: 'vertical'
    padding: 0, dp(6)
    spacing: dp(2)

<Root>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.c_bg
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(58)
        padding: dp(8), dp(6)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
                texture: app.grad
        Button:
            text: '<'
            bold: True
            font_size: '24sp'
            size_hint_x: None
            width: dp(46) if app.can_back else 0
            opacity: 1 if app.can_back else 0
            disabled: not app.can_back
            background_normal: ''
            background_color: 1, 1, 1, 0.15
            on_release: app.back()
        Label:
            text: app.title_text
            bold: True
            font_size: '20sp'
            halign: 'left'
            valign: 'middle'
            text_size: self.size
            shorten: True
    ScreenManager:
        id: sm
    BoxLayout:
        id: undo_bar
        size_hint_y: None
        height: 0
        opacity: 0
        padding: dp(8), dp(4)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 0.15, 0.17, 0.24, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            id: undo_lbl
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Button:
            id: undo_btn
            text: 'ΑΝΑΙΡΕΣΗ'
            bold: True
            size_hint_x: None
            width: dp(120)
            background_normal: ''
            background_color: 0.96, 0.62, 0.0, 1
    BoxLayout:
        id: nav
        size_hint_y: None
        height: dp(64)
        canvas.before:
            Color:
                rgba: app.c_card
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: app.c_line
            Rectangle:
                pos: self.x, self.top - dp(1)
                size: self.width, dp(1)
"""


class NavItem(ButtonBehavior, BoxLayout):
    pass


class Root(BoxLayout):
    pass


class Tap(ButtonBehavior, BoxLayout):
    pass


# ------------------------------------------------------------------ προστασία από κλεισίματα
from kivy.base import ExceptionHandler, ExceptionManager  # noqa: E402


class _Guard(ExceptionHandler):
    def handle_exception(self, inst):
        try:
            import traceback
            L.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(L.DATA_DIR / "errors.log", "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%d/%m %H:%M ") + "".join(
                    traceback.format_exception(type(inst), inst, inst.__traceback__))[-1500:] + "\n")
        except Exception:  # noqa: BLE001
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(_Guard())


def esc(t):
    return str(t).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def gr(x):
    t = f"{x:.1f}".replace(".", ",")
    return t[:-2] if t.endswith(",0") else t


def euro(x):
    return f"{x:.2f}".replace(".", ",") + " €"




def balls_row(nums, color, bonus=None, size_=36):
    row = StackLayout(size_hint_y=None, spacing=dp(5), padding=(0, dp(2)))
    row.bind(minimum_height=row.setter("height"))
    for n in nums:
        row.add_widget(UW.Ball(n, color, size_))
    if bonus is not None:
        row.add_widget(Label(text="+", color=UW.C["ink"], bold=True, size_hint=(None, None), size=(dp(16), dp(size_))))
        row.add_widget(UW.Ball(bonus, JOKER_BALL, size_))
    return row


class LottoApp(App):
    title = "Tzoker Lotto Kino"
    c_bg = ListProperty([0.949, 0.957, 0.973, 1])
    c_card = ListProperty([1, 1, 1, 1])
    c_line = ListProperty([0.88, 0.9, 0.93, 1])
    grad = ObjectProperty(None, allownone=True)
    can_back = BooleanProperty(False)
    title_text = StringProperty("Τζόκερ · Λόττο · ΚΙΝΟ")

    # ================================================================== εκκίνηση
    def build(self):
        L.set_dir(self.user_data_dir)
        UW.set_theme("light")
        self.c_bg, self.c_card, self.c_line = list(UW.C["bg"]), list(UW.C["card"]), list(UW.C["line"])
        Window.clearcolor = UW.C["bg"]
        self.grad = UW.gradient(UW.PRIMARY, UW.PRIMARY2)
        Builder.load_string(KV)
        self.root_w = Root()
        self.sm = self.root_w.ids.sm
        self.sm.transition = NoTransition()
        self.pages = {}
        for name in TITLES:
            scr = Screen(name=name)
            sv = ScrollView(do_scroll_x=False, bar_width=dp(4))
            box = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(12), dp(12)), spacing=dp(12))
            box.bind(minimum_height=box.setter("height"))
            sv.add_widget(box)
            scr.add_widget(sv)
            self.sm.add_widget(scr)
            self.pages[name] = (sv, box)
        self.nav_items = {}
        for key, icon, label in (("home", "home", "Αποτελέσματα"), ("numbers", "list", "Αριθμοί"),
                                 ("check", "barcode", "Έλεγχος"), ("tickets", "user", "Τα δελτία μου")):
            it = NavItem()
            ic = UW.Icon(kind=icon, size_hint_y=None, height=dp(26))
            lb = Label(text=label, font_size=sp(11), size_hint_y=None, height=dp(18))
            it.add_widget(ic)
            it.add_widget(lb)
            it.icon, it.lab = ic, lb
            it.bind(on_release=lambda w, k=key: self.tab(k))
            self.root_w.ids.nav.add_widget(it)
            self.nav_items[key] = it
        self.latest = {}
        self.busy = False
        self.status = ""
        self.game = "joker"
        self.sel = {"numbers": [], "bonus": None}
        self.columns = []          # στήλες του δελτίου που ελέγχεται
        self.code = ""
        self.check_draw = None
        self.gen = []
        self.stack = []
        Window.bind(on_keyboard=self._key)
        self.tab("home")
        Clock.schedule_once(lambda dt: self.refresh_draws(), 0.6)
        return self.root_w

    def on_pause(self):
        return True

    # ================================================================== πλοήγηση
    def page(self, name):
        sv, box = self.pages[name]
        box.clear_widgets()
        sv.scroll_y = 1
        return box

    def show(self, name):
        self.sm.current = name
        self.title_text = TITLES.get(name, "")
        self.can_back = False
        for k, it in self.nav_items.items():
            on = k == name
            col = UW.PRIMARY if on else UW.C["muted"]
            it.icon.rgba = list(col)
            it.lab.color = col
            it.lab.bold = on

    def tab(self, name):
        getattr(self, "build_" + name)()
        self.show(name)

    def back(self):
        if self.sm.current != "home":
            self.tab("home")
            return True
        return False

    def _key(self, win, key, *a):
        if key == 27:
            return self.back()
        return False

    def card(self, box, pad=14):
        c = UW.CardBox(pad=pad)
        box.add_widget(c)
        return c

    def btn(self, parent, text, cb, color=None, fg=(1, 1, 1, 1), h=50):
        b = Button(text=text, bold=True, size_hint_y=None, height=dp(h), background_normal="",
                   background_color=color or UW.PRIMARY, color=fg, font_size=sp(15))
        b.bind(on_release=lambda *a: cb())
        parent.add_widget(b)
        return b

    def ghost(self, parent, text, cb, h=44):
        return self.btn(parent, text, cb, color=UW.C["line"], fg=UW.C["ink"], h=h)

    def game_switch(self, parent, cb):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        for g in L.GAMES:
            on = g == self.game
            b = Button(text=L.GAMES[g]["name"], bold=True, background_normal="",
                       background_color=GCOL[g] if on else UW.C["line"], color=(1, 1, 1, 1) if on else UW.C["ink"])
            b.bind(on_release=lambda w, gg=g: (setattr(self, "game", gg), cb()))
            row.add_widget(b)
        parent.add_widget(row)

    # ================================================================== κληρώσεις
    def refresh_draws(self):
        if self.busy:
            return
        self.busy = True
        self.status = "Λήψη αποτελεσμάτων από τον ΟΠΑΠ…"
        if self.sm.current == "home":
            self.build_home()

        def work():
            latest = T.latest_all()
            wins = []
            try:
                wins = T.settle_tickets()
            except Exception:  # noqa: BLE001
                pass
            Clock.schedule_once(lambda dt: done(latest, wins))

        def done(latest, wins):
            self.busy = False
            self.latest = latest
            ok = [g for g, d in latest.items() if d and "error" not in d]
            self.status = ("Ενημερώθηκε στις " + time.strftime("%H:%M")) if ok else \
                "Δεν ήταν δυνατή η σύνδεση με τον ΟΠΑΠ. Δοκίμασε ξανά."
            self.wins = wins
            if self.sm.current in TABS:
                getattr(self, "build_" + self.sm.current)()

        def watchdog(dt):
            if self.busy:
                self.busy = False
                self.status = "Ο ΟΠΑΠ άργησε να απαντήσει. Δοκίμασε ξανά."
                if self.sm.current == "home":
                    self.build_home()
        Clock.schedule_once(watchdog, 40)
        threading.Thread(target=work, daemon=True).start()

    # ================================================================== ΑΠΟΤΕΛΕΣΜΑΤΑ
    def build_home(self):
        box = self.page("home")
        hero = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(16), dp(14)), spacing=dp(6))
        hero.bind(minimum_height=hero.setter("height"))

        def hbg(*a):
            hero.canvas.before.clear()
            with hero.canvas.before:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=hero.pos, size=hero.size, radius=[dp(22)], texture=self.grad)
        hero.bind(pos=hbg, size=hbg)
        hero.add_widget(UW.text("[b]Κέρδισε το δελτίο μου;[/b]", size=21, color=(1, 1, 1, 1)))
        hero.add_widget(UW.text("Σκάναρε ή γράψε το δελτίο σου και δες αμέσως πόσα κερδίζει.", size=13,
                                color=(1, 1, 1, 0.9)))
        b = Button(text="ΕΛΕΓΧΟΣ ΔΕΛΤΙΟΥ", bold=True, size_hint_y=None, height=dp(50), background_normal="",
                   background_color=(1, 1, 1, 0.25))
        b.bind(on_release=lambda *a: self.tab("check"))
        hero.add_widget(b)
        box.add_widget(hero)
        for t, total in (getattr(self, "wins", None) or []):
            c = self.card(box)
            c.add_widget(UW.text(f"[b]Συγχαρητήρια![/b] Δελτίο {L.GAMES[t['game']]['name']} της {t['created'][:10]}: "
                                 f"κερδίζει [b]{T.euro(total)}[/b]", size=15, color=UW.GOOD))
        st = UW.text(self.status, size=12, color=UW.C["muted"])
        box.add_widget(st)
        for g in L.GAMES:
            d = self.latest.get(g)
            c = self.card(box)
            head = BoxLayout(size_hint_y=None, height=dp(30))
            head.add_widget(UW.Chip(L.GAMES[g]["name"], GCOL[g]))
            head.add_widget(Widget())
            c.add_widget(head)
            if not d:
                c.add_widget(UW.text("Φόρτωση…", color=UW.C["muted"]))
                continue
            if "error" in d:
                c.add_widget(UW.text("Δεν ήρθαν αποτελέσματα.", color=UW.C["muted"]))
                continue
            c.add_widget(UW.text(f"Κλήρωση [b]#{d['id']}[/b] · {d.get('time', '')}", size=13))
            n = L.GAMES[g]["draw"]
            bonus = d["bonus"][0] if (g == "joker" and d.get("bonus")) else None
            c.add_widget(balls_row(sorted(d["numbers"][:n]), GCOL[g], bonus, 34 if g != "kino" else 30))
            if g != "kino" and d.get("prizes"):
                p1 = d["prizes"].get(1, {})
                if p1.get("winners"):
                    c.add_widget(UW.text(f"1η κατηγορία: {p1['winners']} νικητές × {T.euro(p1['amount'])}", size=12))
                elif g == "joker":
                    c.add_widget(UW.text("1η κατηγορία: τζακ-ποτ (κανένας νικητής)", size=12, color=UW.C["muted"]))
            if d.get("next_id"):
                jp = f" · τζακ-ποτ περίπου {T.euro(d['next_jackpot'])}" if d.get("next_jackpot") else ""
                c.add_widget(UW.text(f"Επόμενη κλήρωση #{d['next_id']} {d.get('next_time', '')}{jp}", size=12,
                                     color=UW.C["muted"]))
        self.ghost(box, "Ενημέρωση αποτελεσμάτων", self.refresh_draws)
        box.add_widget(UW.text("Παίζε με μέτρο. Τα τυχερά παιχνίδια είναι για ψυχαγωγία, όχι τρόπος κέρδους.",
                               size=11, color=UW.C["muted"]))

    # ================================================================== ΕΛΕΓΧΟΣ ΔΕΛΤΙΟΥ
    def build_check(self):
        box = self.page("check")
        self.game_switch(box, self._reset_check)
        c = self.card(box)
        c.add_widget(UW.text("[b]1. Σκάναρε το δελτίο[/b] (προαιρετικό)", size=15))
        c.add_widget(UW.text("Ο σαρωτής κρατά τον κωδικό του δελτίου και ανοίγει τον επίσημο έλεγχο του ΟΠΑΠ. Ο "
                             "κωδικός δεν περιέχει τους αριθμούς σου, γι' αυτό γράψε τους στο βήμα 2.", size=12,
                             color=UW.C["muted"]))
        self.btn(c, "ΣΚΑΝΑΡΙΣΜΑ ΜΕ ΤΟΝ ΣΑΡΩΤΗ GOOGLE", self.start_scan, h=48)
        self.scan_lbl = UW.text(f"Κωδικός δελτίου: [b]{self.code}[/b]" if self.code else "", size=13)
        c.add_widget(self.scan_lbl)
        if self.code:
            self.ghost(c, "Επίσημος έλεγχος στον ΟΠΑΠ", lambda: webbrowser.open(T.OPAP_CHECK_URL), h=40)

        g = L.GAMES[self.game]
        c2 = self.card(box)
        need = g["pick"] if self.game != "kino" else 12
        hint = (f"Πάτα {g['pick']} αριθμούς και τον Τζόκερ" if self.game == "joker" else
                f"Πάτα {g['pick']} αριθμούς" if self.game == "lotto" else "Πάτα 1 έως 12 αριθμούς")
        c2.add_widget(UW.text(f"[b]2. Οι αριθμοί της στήλης[/b] · {hint}", size=15))
        grid = GridLayout(cols=9 if g["max"] <= 49 else 10, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for n in range(1, g["max"] + 1):
            on = n in self.sel["numbers"]
            b = Button(text=str(n), bold=on, size_hint_y=None, height=dp(36), background_normal="",
                       background_color=GCOL[self.game] if on else UW.C["line"],
                       color=(1, 1, 1, 1) if on else UW.C["ink"])
            b.bind(on_release=lambda w, nn=n: self._toggle(nn, need))
            grid.add_widget(b)
        c2.add_widget(grid)
        if self.game == "joker":
            c2.add_widget(UW.text("[b]Τζόκερ[/b]", size=14))
            jg = GridLayout(cols=10, spacing=dp(4), size_hint_y=None)
            jg.bind(minimum_height=jg.setter("height"))
            for n in range(1, 21):
                on = n == self.sel["bonus"]
                b = Button(text=str(n), bold=on, size_hint_y=None, height=dp(36), background_normal="",
                           background_color=JOKER_BALL if on else UW.C["line"], color=UW.C["ink"])
                b.bind(on_release=lambda w, nn=n: (self.sel.__setitem__("bonus", nn), self.build_check()))
                jg.add_widget(b)
            c2.add_widget(jg)
        ready = (len(self.sel["numbers"]) == g["pick"] and (self.game != "joker" or self.sel["bonus"])) if \
            self.game != "kino" else (1 <= len(self.sel["numbers"]) <= 12)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        add = Button(text="+ ΣΤΗΛΗ", bold=True, background_normal="", disabled=not ready,
                     background_color=UW.GOOD if ready else UW.C["line"])
        add.bind(on_release=lambda *a: self._add_column())
        clr = Button(text="Καθαρισμός", background_normal="", background_color=UW.C["line"], color=UW.C["ink"])
        clr.bind(on_release=lambda *a: (self.sel.update(numbers=[], bonus=None), self.build_check()))
        row.add_widget(add)
        row.add_widget(clr)
        c2.add_widget(row)
        if self.columns:
            c3 = self.card(box)
            c3.add_widget(UW.text(f"[b]Το δελτίο σου ({len(self.columns)} στήλες)[/b]", size=15))
            for col in self.columns:
                c3.add_widget(balls_row(sorted(col["numbers"]), GCOL[self.game], col.get("bonus"), 30))
            c4 = self.card(box)
            c4.add_widget(UW.text("[b]3. Ποια κλήρωση;[/b]", size=15))
            d = self.latest.get(self.game) or {}
            r = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
            di = TextInput(text=str(self.check_draw or d.get("id") or ""), hint_text="Αριθμός κλήρωσης",
                           input_filter="int", multiline=False)
            r.add_widget(di)
            go = Button(text="ΕΛΕΓΧΟΣ", bold=True, background_normal="", background_color=UW.PRIMARY,
                        size_hint_x=0.45)
            go.bind(on_release=lambda *a: self._check_now(di.text))
            r.add_widget(go)
            c4.add_widget(r)
            if d.get("next_id"):
                self.ghost(c4, f"Αποθήκευση για την επόμενη κλήρωση #{d['next_id']}",
                           lambda: self._save_for(d["next_id"]), h=42)
            self.result_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
            self.result_box.bind(minimum_height=self.result_box.setter("height"))
            box.add_widget(self.result_box)

    def _reset_check(self):
        self.sel = {"numbers": [], "bonus": None}
        self.columns = []
        self.build_check()

    def _toggle(self, n, need):
        nums = self.sel["numbers"]
        if n in nums:
            nums.remove(n)
        elif len(nums) < need:
            nums.append(n)
        self.build_check()

    def _add_column(self):
        self.columns.append({"numbers": sorted(self.sel["numbers"]), "bonus": self.sel["bonus"]})
        self.sel = {"numbers": [], "bonus": None}
        self.build_check()

    def _check_now(self, draw_txt):
        try:
            did = int(draw_txt) if draw_txt.strip() else None
        except ValueError:
            did = None
        self.check_draw = did
        box = self.result_box
        box.clear_widgets()
        box.add_widget(UW.text("Έλεγχος με την επίσημη κλήρωση…", color=UW.C["muted"]))

        def work():
            try:
                d = T.fetch_draw(self.game, did)
                err = None if d else "Η κλήρωση δεν βρέθηκε."
            except Exception as e:  # noqa: BLE001
                d, err = None, f"Δεν ήταν δυνατή η σύνδεση ({str(e)[:60]})."
            Clock.schedule_once(lambda dt: self._show_result(d, err))
        threading.Thread(target=work, daemon=True).start()

    def _show_result(self, d, err):
        box = self.result_box
        box.clear_widgets()
        if err:
            box.add_widget(UW.text(err, color=UW.BAD))
            return
        results, total = T.check_ticket_now(self.game, self.columns, d)
        c = UW.CardBox()
        box.add_widget(c)
        n = L.GAMES[self.game]["draw"]
        bonus = d["bonus"][0] if (self.game == "joker" and d.get("bonus")) else None
        c.add_widget(UW.text(f"Κλήρωση [b]#{d['id']}[/b] · {d.get('time', '')}", size=13))
        c.add_widget(balls_row(sorted(d["numbers"][:n]), GCOL[self.game], bonus, 30))
        if self.game == "kino":
            best = max(r["hits"] for r in results)
            c.add_widget(UW.text(f"[b]Καλύτερη στήλη: {best} επιτυχίες[/b]", size=20, color=UW.PRIMARY))
            c.add_widget(UW.text("Στο ΚΙΝΟ το ποσό εξαρτάται από το πόσους αριθμούς έπαιξες και το ποσό του "
                                 "δελτίου: δες τον πίνακα κερδών στο δελτίο ή στον ΟΠΑΠ.", size=12, color=UW.C["muted"]))
        elif total > 0:
            c.add_widget(UW.text(f"[b]ΚΕΡΔΙΖΕΙ {T.euro(total)}[/b]", size=26, color=UW.GOOD))
        else:
            c.add_widget(UW.text("[b]Δεν κερδίζει αυτή τη φορά[/b]", size=20, color=UW.C["muted"]))
        for i, r in enumerate(results, 1):
            line = f"Στήλη {i}: {r['text']}"
            if r.get("tier"):
                line += f" · κατηγορία {T.ROMAN.get(r['tier'], r['tier'])}"
                if r.get("amount"):
                    line += f" · [b]{T.euro(r['amount'])}[/b]"
            c.add_widget(UW.text(line, size=13))
        c.add_widget(UW.text("Τα ποσά είναι τα επίσημα κέρδη ανά νικητή της κλήρωσης (για βασική στήλη, πριν από "
                             "τυχόν φόρο). Για εξαργύρωση ισχύει πάντα ο έλεγχος του ΟΠΑΠ.", size=11,
                             color=UW.C["muted"]))
        self.btn(c, "ΑΠΟΘΗΚΕΥΣΗ ΣΤΑ ΔΕΛΤΙΑ ΜΟΥ", lambda: self._save_for(d["id"]), color=UW.GOOD, h=44)

    def _save_for(self, draw_id):
        if not self.columns:
            return
        T.add_ticket(self.game, self.columns, draw_id, self.code)
        self.columns = []
        self.code = ""
        self.tab("tickets")
        threading.Thread(target=lambda: (T.settle_tickets(), Clock.schedule_once(
            lambda dt: self.build_tickets() if self.sm.current == "tickets" else None)), daemon=True).start()

    # ---------------------------------------------------------------- σαρωτής
    def start_scan(self):
        if not SC.available():
            self.scan_lbl.text = "Ο σαρωτής λειτουργεί στο κινητό."
            return
        try:
            SC.start()
        except Exception as e:  # noqa: BLE001
            self.scan_lbl.text = f"Ο σαρωτής δεν άνοιξε: {esc(str(e)[:200])}"
            return
        self._scan_t = time.time()
        Clock.schedule_interval(self._scan_poll, 0.25)

    def _scan_poll(self, dt):
        try:
            busy, res, err = SC.poll()
        except Exception:  # noqa: BLE001
            return False
        if busy and time.time() - self._scan_t < 180:
            ph = SC.phase() if hasattr(SC, "phase") else None
            if ph == "install":
                self.scan_lbl.text = "Προετοιμασία του σαρωτή Google (μόνο την πρώτη φορά)…"
            return None
        if res:
            self.code = str(res)
            self.build_check()
        elif err and err != "cancel":
            self.scan_lbl.text = f"Ο σαρωτής απέτυχε: {esc(str(err)[:200])}"
        return False

    # ================================================================== ΤΑ ΔΕΛΤΙΑ ΜΟΥ
    def build_tickets(self):
        box = self.page("tickets")
        ts = T.load_tickets()
        if not ts:
            box.add_widget(UW.text("Δεν έχεις αποθηκευμένα δελτία. Στον «Έλεγχο» γράψε ένα δελτίο και πάτα "
                                   "«Αποθήκευση».", color=UW.C["muted"]))
        total_won = sum(t.get("total") or 0 for t in ts)
        if ts:
            c = self.card(box)
            c.add_widget(UW.text(f"[b]{len(ts)} δελτία[/b] · κέρδη συνολικά [b]{T.euro(total_won)}[/b]", size=15))
            self.ghost(c, "Έλεγχος όλων τώρα", self._settle_all, h=40)
        for t in ts:
            col = {"κερδίζει": UW.GOOD, "δεν κερδίζει": UW.C["muted"]}.get(t["status"], UW.WARN)
            c = self.card(box, pad=12)
            head = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
            head.add_widget(UW.Chip(L.GAMES[t["game"]]["name"], GCOL[t["game"]]))
            head.add_widget(UW.Chip(t["status"].upper() + (f" {T.euro(t['total'])}" if t.get("total") else ""), col))
            head.add_widget(Widget())
            c.add_widget(head)
            c.add_widget(UW.text(f"Κλήρωση #{t.get('draw_id')} · καταχωρίστηκε {t['created']}"
                                 + (f" · κωδικός {esc(t['code'])}" if t.get("code") else ""), size=12,
                                 color=UW.C["muted"]))
            for i, colm in enumerate(t["columns"]):
                c.add_widget(balls_row(sorted(colm["numbers"]), GCOL[t["game"]], colm.get("bonus"), 28))
                if t.get("results"):
                    r = t["results"][i]
                    c.add_widget(UW.text(r["text"] + (f" · [b]{T.euro(r['amount'])}[/b]" if r.get("amount") else ""),
                                         size=12))
            self.ghost(c, "Διαγραφή", lambda tid=t["id"]: (T.delete_ticket(tid), self.build_tickets()), h=34)

    def _settle_all(self):
        def work():
            try:
                T.settle_tickets()
            except Exception:  # noqa: BLE001
                pass
            Clock.schedule_once(lambda dt: self.build_tickets() if self.sm.current == "tickets" else None)
        threading.Thread(target=work, daemon=True).start()

    # ================================================================== ΑΡΙΘΜΟΙ (γεννήτρια)
    def build_numbers(self):
        box = self.page("numbers")
        self.game_switch(box, lambda: (setattr(self, "gen", []), self.build_numbers()))
        c = self.card(box)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.meth = Spinner(text=getattr(self, "_meth", L.METHODS[0]), values=L.METHODS)
        self.ncols = Spinner(text=getattr(self, "_ncols", "3"), values=[str(i) for i in range(1, 11)], size_hint_x=0.35)
        row.add_widget(self.meth)
        row.add_widget(self.ncols)
        c.add_widget(row)
        if self.game == "kino":
            self.kpick = Spinner(text=getattr(self, "_kpick", "6"), values=[str(i) for i in range(1, 13)],
                                 size_hint_y=None, height=dp(42))
            c.add_widget(UW.text("Αριθμοί ΚΙΝΟ ανά στήλη", size=12, color=UW.C["muted"]))
            c.add_widget(self.kpick)
        av = BoxLayout(size_hint_y=None, height=dp(40))
        self.avoid = CheckBox(active=True, size_hint_x=None, width=dp(40), color=UW.C["ink"])
        lb = Label(text="Αποφυγή δημοφιλών συνδυασμών (γενέθλια, σειρές)", color=UW.C["ink"], halign="left",
                   valign="middle")
        lb.bind(size=lambda w, s: setattr(w, "text_size", s))
        av.add_widget(self.avoid)
        av.add_widget(lb)
        c.add_widget(av)
        self.btn(c, "ΒΓΑΛΕ ΑΡΙΘΜΟΥΣ", self._generate)
        if self.gen:
            c2 = self.card(box)
            for col in self.gen:
                c2.add_widget(balls_row(col["numbers"], GCOL[self.game], col["bonus"], 34))
            self.ghost(c2, "Έλεγχος / αποθήκευση αυτών των στηλών", self._gen_to_check, h=42)
        data = L.load(self.game)
        draws = data.get("draws") or []
        c3 = self.card(box)
        if draws:
            st = L.stats(self.game, draws[:200])
            f, gp = st["freq"], st["gap"]
            c3.add_widget(UW.text(f"[b]Στατιστικά {min(200, len(draws))} κληρώσεων[/b]", size=15))
            c3.add_widget(UW.text("Πιο συχνοί:", size=12, color=UW.C["muted"]))
            c3.add_widget(balls_row(st["hot"][:8], UW.GOOD, None, 30))
            c3.add_widget(UW.text("Πιο καθυστερημένοι:", size=12, color=UW.C["muted"]))
            c3.add_widget(balls_row(st["cold"][:8], (0.35, 0.45, 0.6, 1), None, 30))
            _ = (f, gp)
        else:
            c3.add_widget(UW.text("Κατέβασε τις παλιές κληρώσεις για στατιστικά.", size=13, color=UW.C["muted"]))
        self.ghost(c3, "Ενημέρωση ιστορικού κληρώσεων", self._fetch_history, h=40)
        self.hist_lbl = UW.text("", size=12, color=UW.C["muted"])
        c3.add_widget(self.hist_lbl)
        box.add_widget(UW.text(L.odds_text(self.game, int(getattr(self, "_kpick", "6")) if self.game == "kino" else None)
                               + ". Κάθε κλήρωση είναι τυχαία: τα στατιστικά δεν προβλέπουν την επόμενη.",
                               size=11, color=UW.C["muted"]))

    def _generate(self):
        self._meth, self._ncols = self.meth.text, self.ncols.text
        pick = None
        if self.game == "kino":
            self._kpick = self.kpick.text
            pick = int(self._kpick)
        draws = (L.load(self.game).get("draws") or [])[:200]
        method = self._meth if draws else "Εντελώς τυχαία"
        self.gen = L.generate(self.game, draws, method, int(self._ncols), pick, self.avoid.active)
        self.build_numbers()

    def _gen_to_check(self):
        self.columns = [{"numbers": c["numbers"], "bonus": c["bonus"]} for c in self.gen]
        self.sel = {"numbers": [], "bonus": None}
        self.tab("check")

    def _fetch_history(self):
        game = self.game
        self.hist_lbl.text = "Λήψη κληρώσεων…"

        def work():
            try:
                draws = L.fetch_history(game, 300, lambda m: None)
                L.save(game, draws)
                msg = f"Αποθηκεύτηκαν {len(draws)} κληρώσεις."
            except Exception as e:  # noqa: BLE001
                msg = f"Αποτυχία: {str(e)[:80]}"
            Clock.schedule_once(lambda dt: (self.build_numbers(), setattr(self.hist_lbl, "text", msg))
                                if self.sm.current == "numbers" else None)
        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    LottoApp().run()
