import mimetypes
import os
import shutil
from http import HTTPStatus
from pathlib import Path

from flask import Flask, render_template, request, redirect, Response, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

from serverprocess import ServerProcess

app = Flask(__name__)
sio = SocketIO(app, cors_allowed_origins="*")  # 実際の設定に

# ファイルエクスプローラのRootディレクトリ (これより上の階層には移動できない(はず))
FILE_EXPLORER_ROOT = Path("D:\\Minecraft Launcher 4").resolve()

test_server = ServerProcess("java", "-Xmx128M", "-Xms128M", "-jar", "paper-1.8.8-445.jar",
                            cwd="P:\\tmpTinySpigot")


def is_safe_path(path: Path):
    """
    与えられたパスが安全かチェックする
    """
    try:
        # 一度パスを絶対パス化してから、rootパスで相対パス化する
        # relative_to にrootパスより階層が高いパスが与えられるとValueErrorが発生する
        (FILE_EXPLORER_ROOT / path).resolve().relative_to(FILE_EXPLORER_ROOT)
    except ValueError:
        return False
    return True


def normalize_path(path: Path):
    """
    パスをrootパスからの相対パスに正規化する
    """
    return (FILE_EXPLORER_ROOT / path).resolve().relative_to(FILE_EXPLORER_ROOT)


def sorted_iterdir(path: Path):
    """
    与えられたパスの内容をソートして返す
    並びはフォルダを最優先し、大文字小文字を区別しないアルファベット順 (Windows風)
    """
    return sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))


@app.route("/fileexplorer")
def file_explorer():
    """
    ファイルエクスプローラのページ処理

    引数:
      GET ./?p=(フォルダパス)
    """
    current_dir = Path(request.args.get("p") or FILE_EXPLORER_ROOT)

    # 存在しないパスだったら、安全な限り存在する上の階層に移動する
    while not (FILE_EXPLORER_ROOT / current_dir).exists() and is_safe_path(current_dir):
        current_dir = current_dir / ".."

    # 安全なパスではなかったら、rootパスにリダイレクト
    if not is_safe_path(current_dir):
        return redirect("?p=.")

    current_dir = normalize_path(current_dir)

    _args = dict(
        Path=Path,
        root=FILE_EXPLORER_ROOT,
        cwd=current_dir.as_posix(),
        sorted_iterdir=sorted_iterdir
    )
    return render_template('fileexplorer.html', **_args)


@app.route("/fio", methods=["GET", "POST", "DELETE"])
def file_io():
    """
    ファイルの入出力

    引数:
      GET    ./?p=(ダウンロードするファイルのパス)
      POST   ./?d=(アップロード先のフォルダパス)
      DELETE ./?p=(削除するファイルのパス)
    """
    if request.method == "DELETE":  # delete
        # 引数の確認
        path = request.args.get("p")  # 削除するファイルパスを指定
        if not path:
            return Response("Path not specified", status=HTTPStatus.BAD_REQUEST)

        # パスの確認
        path = Path(path)
        if not is_safe_path(path) or not path.exists():
            return Response("Invalid path", status=HTTPStatus.FORBIDDEN)

        try:
            if path.is_dir():
                shutil.rmtree(FILE_EXPLORER_ROOT / path)
            else:
                os.remove(FILE_EXPLORER_ROOT / path)
        except Exception:
            raise

        # 問題がなければ、削除ファイルの元フォルダを開かせる
        current_dir = normalize_path(path)
        return redirect(f"./fileexplorer?p={current_dir.as_posix()}")

    elif request.method == "POST":  # upload
        # 引数の確認
        out_dir = request.args.get("d")  # アップロード先ディレクトリパスを指定
        if not out_dir:
            return Response("Directory not specified", status=HTTPStatus.BAD_REQUEST)

        # パスの確認
        out_dir = Path(out_dir)
        if not is_safe_path(out_dir):
            return Response("Invalid path", status=HTTPStatus.FORBIDDEN)

        # 送信ファイルの確認
        file = request.files["file"]
        if not file:
            return Response("File name is empty", status=HTTPStatus.BAD_REQUEST)

        # 送信ファイルの書き出し
        file.save(FILE_EXPLORER_ROOT / out_dir / secure_filename(file.filename))

        # 問題がなければ、アップロード先のフォルダを開かせる
        current_dir = normalize_path(out_dir)
        return redirect(f"./fileexplorer?p={current_dir.as_posix()}")

    else:  # download
        # 引数の確認
        path = request.args.get("p")  # ダウンロードするファイルの対象パスを指定
        if not path:
            return Response("Path not specified", status=HTTPStatus.BAD_REQUEST)

        # パスの確認
        path = Path(path)
        if not is_safe_path(path) or (FILE_EXPLORER_ROOT / path).is_dir():
            return Response("Invalid path", status=HTTPStatus.FORBIDDEN)

        # ファイル出力
        return send_file(FILE_EXPLORER_ROOT / path, mimetype=mimetypes.guess_extension(path.name))


@app.route("/fcp")
def file_copy():
    """
    ファイルのコピー

    引数:
      GET ./?s=(コピー元)&d=(コピー先)
    """
    # 引数の確認
    source_path = request.args.get("s")  # コピー元のパス
    to_path = request.args.get("d")  # コピー先のパス

    if not source_path:
        return Response("Path(s) not specified", status=HTTPStatus.BAD_REQUEST)
    if not to_path:
        return Response("Path(d) not specified", status=HTTPStatus.BAD_REQUEST)

    # パスの確認
    source_path = Path(source_path)
    if not is_safe_path(source_path) or not source_path.is_file():
        return Response("Invalid source(s) path", status=HTTPStatus.FORBIDDEN)
    to_path = Path(to_path)
    if not is_safe_path(to_path) or not to_path.is_file():
        return Response("Invalid destination(d) path", status=HTTPStatus.FORBIDDEN)

    # ファイルのコピー
    try:
        shutil.copy(FILE_EXPLORER_ROOT / source_path, FILE_EXPLORER_ROOT / to_path)
    except Exception:
        raise

    # 問題がなければ、コピー先ファイルのフォルダを開かせる
    current_dir = normalize_path(to_path.parent)
    return redirect(f"./fileexplorer?p={current_dir.as_posix()}")


@app.route("/console")
def console():
    return render_template("console.html")


@sio.on("connect")
def _ws_connect(_):
    # hard split
    data = test_server.stdin_content[-1000 * 1000:].decode("utf-8", errors="ignore")
    emit("term_data", dict(raw=data))


@sio.on("disconnect")
def _ws_disconnect():
    pass


@sio.on("term_send_text")
def _ws_term_send_text(data):
    text = data["text"].strip()
    if not text:
        return
    emit("term_data", dict(raw=f"[WebConsole]: /{text}\n\r"), broadcast=True)
    test_server.write(text + "\n")


if __name__ == "__main__":
    def _send(data: bytes):
        sio.emit("term_data", dict(raw=data.decode("utf-8")))

    test_server.add_stdin_listener(_send)
    test_server.start()

    sio.run(app, debug=False, use_evalex=False, allow_unsafe_werkzeug=True)
