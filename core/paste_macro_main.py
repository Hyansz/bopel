if __name__ == '__main__':
    import argparse, json, sys
    from core.paste_macro import pilih_screenshot_paste
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry', action='store_true', help='dry run: list selected screenshots and captions')
    args = parser.parse_args()
    if args.dry:
        items = pilih_screenshot_paste()
        for path, caption in items:
            print(json.dumps({'path': path, 'caption': caption}))
    else:
        print('Run with --dry for dry run.')
        sys.exit(0)

