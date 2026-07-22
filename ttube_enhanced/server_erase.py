
@app.route("/api/erase_data", methods=["POST"])
def erase_data():
    try:
        ttube_dir = os.path.join(os.path.expanduser("~"), "Music", "TTube")
        if os.path.exists(ttube_dir):
            import shutil
            shutil.rmtree(ttube_dir)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
