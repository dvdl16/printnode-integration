## Printnode Integration

Integration with Printnode API

### Installation

To avoid errors, I've removed the PrintNode Python library from `requirements.txt`. This means you have to install it manually before installing this app:

```bash
cd frappe-bench
./env/bin/pip install -e git+https://github.com/PrintNode/PrintNode-Python.git#egg=printnodeapi
```

#### License

MIT
