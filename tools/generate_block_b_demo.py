"""Regenerate the synthetic demo bundle (no network access)."""
from investresearch.demo_dataset import create

if __name__ == '__main__':
    result=create()
    print('Generated synthetic Block B bundle:',len(result['assets']),'assets')
