import mimetypes
from http import HTTPStatus
from pathlib import Path

from flask import Flask, render_template, request, redirect, Response, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ファイルエクスプローラのRootディレクトリ (これより上の階層には移動できない(はず))
FILE_EXPLORER_ROOT = Path("D:\\Minecraft Launcher 4").resolve()


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
        return Response("Not implemented", status=HTTPStatus.SERVICE_UNAVAILABLE)

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


if __name__ == "__main__":
    app.run()