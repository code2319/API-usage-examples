from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


async def foo(start_date, end_date):
    return start_date, end_date


async def a(start_date, end_date):
    data = await foo(start_date, end_date)
    return data


@celery.task
def async_task_to_sync(start_date, end_date):
    from asgiref.sync import async_to_sync

    return async_to_sync(a)(start_date, end_date)


@app.route("/trigger-task", methods=["POST"])
def trigger_task():
    request_data = request.json
    start_date = request_data.get("start_date")
    end_date = request_data.get("end_date")

    res = async_task.delay(start_date, end_date)
    return jsonify({"task_id": res.id}), 202


@app.route("/task-status/<task_id>")
def task_status(task_id):
    res = async_task.AsyncResult(task_id)
    if res.ready():
        if res.status == "SUCCESS":
            return jsonify({"status": res.status, "result": res.result}), 200
        else:
            return jsonify({"status": "failed"}), 400
    else:
        return jsonify({"status": "pending"}), 202


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
