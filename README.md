# cs5270-widgets

Consumer program for CS5270 HW6.

## Build
Requires Python 3.11+.
```
python -m venv .venv
source .venv/bin/activate       
pip install -r requirements.txt
```
AWS credentials are read from `~/.aws/credentials`.

## Run
Replace the uppercase placeholders with your own resource names.

Store widgets in S3:
```
python -m widget_consumer.cli --request-bucket REQUEST_BUCKET --storage s3 --widget-bucket WIDGET_BUCKET
```
Store widgets in DynamoDB:
```
python -m widget_consumer.cli --request-bucket REQUEST_BUCKET --storage dynamodb --table TABLE_NAME --key-name KEY_NAME
```
See all options: `python -m widget_consumer.cli --help`

The Consumer stops after `--max-empty-polls` consecutive empty polls or when the user presses Ctrl+C. 

## Test
```
pytest tests/unit
```

## Credits
- https://refactoring.guru/design-patterns/factory-method
- Libraries: boto3, Click, pytest, pytest-cov, moto.