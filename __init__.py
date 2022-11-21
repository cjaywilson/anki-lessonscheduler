from random import randint

from anki.consts import QUEUE_TYPE_SUSPENDED
from aqt import QAction, QInputDialog, QMessageBox, gui_hooks, mw, qconnect

need_refresh = False
added_lesson = False
conf = mw.addonManager.getConfig(__name__)

def setup():
    # Prompt user to set up
    diag = QMessageBox.question(mw, "Setup Addon", "Would you like to set up the Lesson Scheduler?")
    if diag == QMessageBox.StandardButton.No:
        return

    # Configure the deck and field
    while True:
        deck, ok = QInputDialog.getItem(mw, "Select Deck", "Please select the deck to schedule", [d.name for d in mw.col.decks.all_names_and_ids()], editable=False)
        if not ok:
            return
        
        notes = set([mw.col.get_note(id).note_type()["id"] for id in mw.col.find_notes(f"\"deck:{deck}\"")])
        if len(notes) > 1:
            QMessageBox.warning(mw, "Invalid Deck", f"{deck!r} contains more than 1 note type!")
        else:
            break
    
    field, ok = QInputDialog.getItem(mw, "Select Field", "Please select the note's lesson field",
        mw.col.field_names_for_note_ids(mw.col.find_notes(f"\"deck:{deck}\"")[0:1]), editable=False)
    
    if not ok:
        return

    conf["deck"] = deck
    conf["field"] = field

    # Create a new options group and apply it to the deck
    all_configs = set( [c["name"] for c in mw.col.decks.all_config()] )
    conf_name = "Lesson Scheduler "

    if conf_name in all_configs and \
        QMessageBox.question(mw, "Overwrite Options", f"{conf_name!r} already exists. Would you like to overwrite this configuration?") == QMessageBox.StandardButton.Yes:
        conf_dict = [c for c in mw.col.decks.all_config() if c["name"] == conf_name][0]
        conf_id = conf_dict["id"]
    else:
        while conf_name in all_configs:
            conf_name += str(randint(0, 9))
        
        conf_id = mw.col.decks.add_config_returning_id(conf_name)
        conf_dict = mw.col.decks.get_config(conf_id)

    conf_dict["new"]["perDay"] = 9999
    conf_dict["rev"]["perDay"] = 9999

    mw.col.decks.update_config(conf_dict)
    mw.col.decks.set_config_id_for_deck_dict(
        mw.col.decks.by_name(conf["deck"]), conf_id
    )

    # Reset all cards in the deck
    mw.col.sched.reset_cards(
        mw.col.find_cards(f"\"deck:{conf['deck']}\"")
    )
    
    # Suspend all cards except the first lesson
    mw.col.sched.suspend_cards(
        mw.col.find_cards(f"\"deck:{conf['deck']}\" -\"{conf['field']}:1\"")
    )
    
    # Flag setup complete
    if not conf["setup"]:
        hook()
    
    conf["setup"] = True
    mw.addonManager.writeConfig(__name__, conf)

    # Refresh the browser to reflect changes
    mw.deckBrowser.refresh()

def add_lesson(overview, content):
    global need_refresh, added_lesson

    # Check the current deck
    if added_lesson or content.deck != conf["deck"]:
        return

    # Find which lesson to add
    max_lesson = 0
    max_lesson_active = 0

    # TODO: find a faster way to do this
    for id in mw.col.find_cards(f"\"deck:{conf['deck']}\""):
        card = mw.col.get_card(id)
        note = card.note()

        max_lesson = max(max_lesson, int(note[conf["field"]]))

        if card.queue != QUEUE_TYPE_SUSPENDED:
            max_lesson_active = max(max_lesson_active, int(note[conf["field"]]))
    
    if max_lesson_active == max_lesson:
        return
    
    # Prompt user to add the lesson
    diag = QMessageBox.question(mw, "Add Lesson", f"Add Lesson {max_lesson_active + 1} cards?")
    if diag == QMessageBox.StandardButton.No:
        return

    # Unsuspend cards for the lesson
    mw.col.sched.unsuspend_cards(
        mw.col.find_cards(f"\"deck:{conf['deck']}\" \"{conf['field']}:{max_lesson_active + 1}\"")
    )

    # Force overview refresh to reflect changes
    added_lesson = True
    need_refresh = True

def lesson_refresh(overview):
    global need_refresh
    
    if need_refresh:
        need_refresh = False
        mw.overview.refresh()

def hook():
    gui_hooks.overview_will_render_content.append(add_lesson)
    gui_hooks.overview_did_refresh.append(lesson_refresh)

def unlock_lesson():
    global added_lesson
    added_lesson = False
    mw.deckBrowser.refresh()

# Initialize config file
if not conf:
    conf = {}

if not "setup" in conf:
    conf["setup"] = False

# Setup addon hook
if conf["setup"]:
    hook()

# TODO: push these into a sub-menu
# Add setup button to the toolbar
action = QAction("Setup lesson scheduler", mw)
qconnect(action.triggered, setup)
mw.form.menuTools.addAction(action)

# Add unlock button to the toolbar
action2 = QAction("Unlock another lesson", mw)
qconnect(action2.triggered, unlock_lesson)
mw.form.menuTools.addAction(action2)
