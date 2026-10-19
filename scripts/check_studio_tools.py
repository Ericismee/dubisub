"""Playwright interaction regression with controlled task API fixtures, not AI output."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def main():
    project={'id':'tools-fixture','name':'Studio tools fixture','mode':'full','target_language':'vi','revision':0,'tracks':[{'id':'track','kind':'manual','language':'vi','cues':[{'id':'c1','start_ms':0,'end_ms':1000,'text':'Bản gốc'}]}],'assets':[],'jobs_order':'oldest_first','jobs':[
        {'id':'old','kind':'narrate','state':'succeeded','attempts':1,'progress':100,'error':None},
        {'id':'middle','kind':'transcribe','state':'failed','attempts':1,'progress':10,'error':'Lỗi fixture','can_retry':True},
        {'id':'new','kind':'render','state':'queued','attempts':0,'progress':0,'error':None}]}
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1543,'height':884});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def fixture(route):
            path=route.request.url.split('/api/',1)[1]
            if path=='projects':value=[project]
            elif path=='projects/tools-fixture':value=project
            elif path=='projects/tools-fixture/tracks/track' and route.request.method=='PUT':
                project['tracks'][0]['cues']=route.request.post_data_json['cues'];project['revision']+=1;value=project
            elif path=='jobs/new/cancel':project['jobs'][-1]['state']='canceled';value={'status':'cancel'}
            elif path=='jobs/new' and route.request.method=='DELETE':project['jobs']=[j for j in project['jobs'] if j['id']!='new'];value={'outputs_preserved':True}
            else:route.fallback();return
            route.fulfill(status=200,content_type='application/json',body=json.dumps(value))
        page.route('**/api/**',fixture)
        page.goto('http://127.0.0.1:3600/');page.locator('.project-open').click()
        page.get_by_role('button',name='Tác vụ',exact=True).click();dialog=page.locator('.tasks-dialog');expect(dialog).to_be_visible()
        expect(dialog.locator('.jobs>div').first.locator('strong')).to_have_text('Xuất MP4')
        dialog.get_by_role('button',name='Hủy',exact=True).click()
        dialog.locator('.task-filters button').nth(5).click();expect(dialog.locator('.jobs>div')).to_have_count(1)
        dialog.get_by_role('button',name='Xóa lịch sử tác vụ new').click();expect(dialog.locator('.jobs>div')).to_have_count(0)
        dialog.locator('.task-filters button').nth(4).click();expect(dialog.locator('.jobs>div')).to_have_count(1)
        dialog.get_by_label('Loại tác vụ',exact=True).select_option('transcribe');expect(dialog.locator('.jobs>div')).to_have_count(1)
        Path('test-results').mkdir(exist_ok=True);page.screenshot(path='test-results/tasks-regression.png')
        page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
        page.locator('.toolrail>button').nth(2).click()
        cue=page.get_by_label('Câu 1',exact=True)
        with page.expect_response(lambda r:'/tracks/track' in r.url and r.request.method=='PUT'):
            cue.fill('Bản sửa thử')
        project['revision']+=1  # A background job changes metadata, not cue content.
        page.wait_for_timeout(1900)
        undo=page.get_by_role('button',name='Hoàn tác',exact=True);expect(undo).to_be_enabled()
        with page.expect_response(lambda r:'/tracks/track' in r.url and r.request.method=='PUT'):
            undo.click()
        expect(cue).to_have_value('Bản gốc')
        page.locator('.workspace-tabs button').nth(1).click();expect(page.locator('.studio-drawer')).to_be_visible()
        page.locator('.workspace-tabs button').nth(5).click();expect(page.locator('.studio-drawer')).not_to_be_visible()
        for size in ({'width':700,'height':884},{'width':390,'height':844}):
            page.set_viewport_size(size);page.locator('.workspace-tabs button').nth(1).click()
            expect(page.locator('.studio-drawer')).to_be_visible()
            assert page.locator('.studio-drawer').bounding_box()['width']<=size['width']
            page.keyboard.press('Escape')
        assert not errors,errors
        browser.close();print('Task filters/cancel/history removal, undo across background revision, toolbar drawer, Escape and responsive widths passed (controlled API fixtures).')


if __name__=='__main__':main()
